"""
Test FAISS approximate nearest neighbor search performance vs. exhaustive search.

This script demonstrates the speedup needed for production similarity matching
at scale. Uses synthetic patient data to compare:
- Current: O(n) exhaustive cosine similarity
- Proposed: O(log n) FAISS approximate nearest neighbor

Usage:
    pip install faiss-cpu numpy
    python ml/test_faiss_similarity.py --file=demo_patients.json --scale
"""

import json
import numpy as np
import time
import argparse
from typing import Tuple, List


class FeatureExtractor:
    """Extract normalized feature vectors from patient data."""
    
    @staticmethod
    def extract_features(patient: dict) -> np.ndarray:
        """
        Create a feature vector from patient data.
        
        Features (simplified for demo):
        - Age (normalized)
        - Gender (0/1)
        - Blood group type (encoded)
        - Vital sign averages (normalized)
        - Diagnosis codes (binary: presence of condition)
        """
        from datetime import datetime
        
        # Age (0-100 → 0-1)
        dob = datetime.strptime(patient['date_of_birth'], '%Y-%m-%d')
        age = (datetime.now() - dob).days / (85 * 365)
        age = min(1.0, age)
        
        # Gender (male=0, female=1)
        gender = 1.0 if patient['gender'] == 'female' else 0.0
        
        # Blood group encoding
        blood_group_map = {
            'O+': 0.0, 'O-': 0.1, 'A+': 0.2, 'A-': 0.3,
            'B+': 0.4, 'B-': 0.5, 'AB+': 0.6, 'AB-': 0.7
        }
        blood_group = blood_group_map.get(patient['blood_group'], 0.5)
        
        # Average vitals from encounters
        vitals_list = []
        for enc in patient['encounters']:
            v = enc['vitals']
            vitals_list.append([
                v['temperature_celsius'] / 40.0,  # Normalize 0-40°C → 0-1
                v['systolic_bp'] / 200.0,          # Normalize 0-200 → 0-1
                v['heart_rate'] / 150.0,           # Normalize 0-150 → 0-1
                v['respiratory_rate'] / 30.0,      # Normalize 0-30 → 0-1
                v['spo2_percent'] / 100.0,         # Normalize 0-100 → 0-1
            ])
        
        if vitals_list:
            avg_vitals = np.mean(vitals_list, axis=0)
        else:
            avg_vitals = np.zeros(5)
        
        # Diagnoses (binary: presence of condition)
        diagnoses = np.zeros(10)  # 10 common diagnoses
        diagnosis_map = {
            'B54': 0,  # Malaria
            'I10': 1,  # Hypertension
            'E11': 2,  # Diabetes
            'D57': 3,  # Sickle cell
            'J45': 4,  # Asthma
            'B20': 5,  # HIV
            'J00': 6,  # Cold
            'A09': 7,  # Diarrhea
            'K21': 8,  # GERD
            'M79.3': 9,  # Myalgia
        }
        
        for enc in patient['encounters']:
            for dx in enc['diagnoses']:
                idx = diagnosis_map.get(dx['icd10_code'])
                if idx is not None:
                    diagnoses[idx] = 1.0
        
        # Combine all features
        features = np.concatenate([
            [age, gender, blood_group],
            avg_vitals,
            diagnoses
        ])
        
        # Normalize to unit vector for cosine similarity
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm
        
        return features.astype('float32')


class SimilaritySearchBenchmark:
    """Benchmark exhaustive vs. FAISS similarity search."""
    
    def __init__(self, features: np.ndarray, patient_ids: List[str]):
        self.features = features
        self.patient_ids = patient_ids
        self.n_patients = len(features)
        self.dimension = features.shape[1]
    
    def exhaustive_search(self, query_idx: int, k: int = 5) -> Tuple[List[int], List[float], float]:
        """
        Exhaustive O(n) cosine similarity search.
        (Current approach in MedSync)
        """
        start = time.time()
        
        query_vector = self.features[query_idx]
        similarities = np.dot(self.features, query_vector)
        
        # Get top-k indices
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        top_k_scores = similarities[top_k_indices]
        
        elapsed = time.time() - start
        
        return list(top_k_indices), list(top_k_scores), elapsed
    
    def faiss_search(self, query_idx: int, k: int = 5) -> Tuple[List[int], List[float], float]:
        """
        FAISS approximate nearest neighbor search.
        (Proposed optimization)
        """
        try:
            import faiss
        except ImportError:
            print("\n❌ FAISS not installed. Install with: pip install faiss-cpu")
            return None, None, None
        
        start = time.time()
        
        # Create and populate index
        index = faiss.IndexFlatIP(self.dimension)
        index.add(self.features)
        
        # Search
        query_vector = np.array([self.features[query_idx]], dtype='float32')
        distances, indices = index.search(query_vector, k)
        
        elapsed = time.time() - start
        
        return list(indices[0]), list(distances[0]), elapsed
    
    def benchmark(self, k: int = 5, iterations: int = 100) -> dict:
        """Run benchmark comparing both methods."""
        
        print(f"\n🔍 SIMILARITY SEARCH BENCHMARK")
        print(f"{'=' * 70}")
        print(f"Dataset: {self.n_patients} patients")
        print(f"Features: {self.dimension}-dimensional vectors")
        print(f"Search: Top-{k} similar patients")
        print(f"Iterations: {iterations}")
        
        # Test on random patients
        test_indices = np.random.choice(self.n_patients, min(iterations, self.n_patients), replace=False)
        
        exhaustive_times = []
        faiss_times = []
        consistency_check = True
        
        for i, idx in enumerate(test_indices):
            # Exhaustive search
            exc_indices, exc_scores, exc_time = self.exhaustive_search(idx, k)
            exhaustive_times.append(exc_time)
            
            # FAISS search
            faiss_indices, faiss_scores, faiss_time = self.faiss_search(idx, k)
            if faiss_indices is None:
                return None
            
            faiss_times.append(faiss_time)
            
            # Check consistency (top result should be same)
            if exc_indices[0] != faiss_indices[0]:
                consistency_check = False
            
            if (i + 1) % 20 == 0:
                print(f"  Completed {i + 1}/{len(test_indices)} iterations...")
        
        # Calculate statistics
        exc_mean = np.mean(exhaustive_times) * 1000  # Convert to ms
        exc_std = np.std(exhaustive_times) * 1000
        exc_max = np.max(exhaustive_times) * 1000
        
        faiss_mean = np.mean(faiss_times) * 1000
        faiss_std = np.std(faiss_times) * 1000
        faiss_max = np.max(faiss_times) * 1000
        
        speedup = exc_mean / faiss_mean if faiss_mean > 0 else 0
        
        print(f"\n📊 RESULTS")
        print(f"{'=' * 70}")
        print(f"\nExhaustive Search (Current):")
        print(f"  Mean:     {exc_mean:.3f} ms ± {exc_std:.3f} ms")
        print(f"  Max:      {exc_max:.3f} ms")
        print(f"  Per query: {exc_mean:.2f} ms")
        
        print(f"\nFAISS Search (Proposed):")
        print(f"  Mean:     {faiss_mean:.3f} ms ± {faiss_std:.3f} ms")
        print(f"  Max:      {faiss_max:.3f} ms")
        print(f"  Per query: {faiss_mean:.2f} ms")
        
        print(f"\nSpeedup:")
        print(f"  {speedup:.1f}x faster with FAISS")
        
        print(f"\nConsistency:")
        print(f"  Top result matches: {'✅ YES' if consistency_check else '⚠️  SOMETIMES'}")
        
        return {
            'exhaustive_mean_ms': exc_mean,
            'faiss_mean_ms': faiss_mean,
            'speedup': speedup,
            'consistency': consistency_check,
        }
    
    def project_scale(self):
        """Project performance at larger scales."""
        
        print(f"\n📈 SCALING PROJECTIONS")
        print(f"{'=' * 70}")
        print(f"\nAssuming linear scaling for exhaustive, logarithmic for FAISS:")
        print(f"(These are projections, not actual measurements)\n")
        
        # Get baseline from small dataset
        exc_indices, exc_scores, exc_time = self.exhaustive_search(0)
        faiss_indices, faiss_scores, faiss_time = self.faiss_search(0)
        
        if faiss_time is None:
            return
        
        print(f"{'Patients':>12} {'Exhaustive':>15} {'FAISS':>15} {'Speedup':>10} {'Status':>15}")
        print(f"{'-' * 70}")
        
        scales = [150, 500, 1000, 5000, 10000, 50000, 100000, 1000000]
        
        for scale in scales:
            # Linear scaling: exhaustive time *= (scale / current_scale)
            exc_proj = exc_time * (scale / self.n_patients) * 1000
            
            # Log scaling: faiss_time += log(scale) term
            faiss_proj = faiss_time * (1 + np.log(scale) / np.log(self.n_patients)) * 1000
            
            speedup_proj = exc_proj / faiss_proj if faiss_proj > 0 else 0
            
            # Determine status
            if exc_proj > 1000:  # > 1 second
                status = "❌ Unacceptable"
            elif exc_proj > 500:
                status = "⚠️  Slow"
            else:
                status = "✅ Ok"
            
            print(f"{scale:>12,d} {exc_proj:>14.1f}ms {faiss_proj:>14.1f}ms {speedup_proj:>9.1f}x {status:>15}")
        
        print(f"\n💡 Key Insight:")
        print(f"   At 100k patients, exhaustive search would be ~{exc_time * (100000/self.n_patients) * 1000:.0f}ms")
        print(f"   At 100k patients, FAISS would be ~{(faiss_time * (1 + np.log(100000)/np.log(self.n_patients))) * 1000:.1f}ms")
        print(f"   This is why FAISS is essential for production!")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark FAISS vs exhaustive similarity search"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="medsync-backend/data/seeds/demo_patients.json",
        help="Path to synthetic data JSON file"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of similar patients to find"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of benchmark iterations"
    )
    parser.add_argument(
        "--scale",
        action="store_true",
        help="Show scaling projections to larger datasets"
    )
    
    args = parser.parse_args()
    
    # Load data
    print(f"📂 Loading {args.file}...")
    with open(args.file) as f:
        data = json.load(f)
    
    patients = data['patients']
    patient_ids = [p['ghana_health_id'] for p in patients]
    
    # Extract features
    print(f"🔧 Extracting features from {len(patients)} patients...")
    features_list = []
    for patient in patients:
        feat = FeatureExtractor.extract_features(patient)
        features_list.append(feat)
    
    features = np.array(features_list, dtype='float32')
    print(f"   Feature dimension: {features.shape[1]}")
    
    # Run benchmark
    benchmark = SimilaritySearchBenchmark(features, patient_ids)
    results = benchmark.benchmark(k=args.k, iterations=args.iterations)
    
    if results:
        print(f"\n{'=' * 70}")
        print(f"✅ BENCHMARK COMPLETE")
        if args.scale:
            benchmark.project_scale()
    
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
