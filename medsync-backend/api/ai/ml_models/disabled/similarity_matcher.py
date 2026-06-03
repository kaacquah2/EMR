"""
Patient Similarity Engine.

Finds similar patient cases for treatment outcome benchmarking.

Uses k-NN with cosine similarity for finding comparable cases.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np
from sklearn.preprocessing import StandardScaler
from api.ai.faiss_indexer import FaissIndexer

logger = logging.getLogger(__name__)


class SimilarityMatcher:
    """
    k-NN patient similarity matcher for finding comparable cases.
    """

    # Features to use for similarity matching
    SIMILARITY_FEATURES = [
        'age',
        'gender_male',
        'gender_female',
        'bp_systolic_mean',
        'bp_diastolic_mean',
        'pulse_mean',
        'spo2_mean',
        'weight_mean',
        'bmi_mean',
        'active_medication_count',
        'comorbidity_index',
        'chronic_condition_count',
        'has_diabetes',
        'has_hypertension',
        'has_heart_disease',
        'has_kidney_disease',
        'has_copd',
    ]

    def __init__(self, dimension: int = 17):  # Default 17 based on SIMILARITY_FEATURES
        """Initialize similarity matcher."""
        self.scaler = StandardScaler()
        self.dimension = dimension
        self.indexer = FaissIndexer(dimension=dimension)
        self.patient_data_cache: Dict[str, Dict[str, Any]] = {}
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'algorithm': 'FAISS Approximate Nearest Neighbor (Inner Product)',
            'num_features': dimension,
        }
        logger.info(f"Similarity matcher initialized with FAISS, dimension={dimension}")

    def index_patients(self, all_patient_features: List[Dict[str, Any]]):
        """
        Index all patients for similarity searches using FAISS.
        """
        try:
            if not all_patient_features:
                logger.warning("No patient data to index")
                return

            # Store in cache for metadata retrieval
            self.patient_data_cache = {p['patient_id']: p for p in all_patient_features}

            # Extract feature matrix
            feature_matrix = []
            patient_ids = []
            for patient_data in all_patient_features:
                vector = self._extract_feature_vector(patient_data)
                feature_matrix.append(vector)
                patient_ids.append(patient_data['patient_id'])

            # Scale and build FAISS index
            feature_matrix = np.array(feature_matrix)
            scaled_matrix = self.scaler.fit_transform(feature_matrix)
            
            self.indexer.build_index(
                scaled_matrix.astype('float32'),
                patient_ids,
                metadata=all_patient_features
            )
            
            logger.info(f"FAISS indexed {len(all_patient_features)} patients")

        except Exception as e:
            logger.error(f"Error indexing patients: {e}")
            raise

    def save_to_disk(self, path: str):
        """Save FAISS index and scaler to disk."""
        try:
            self.indexer.save_index(path)
            # Also save the scaler and data cache
            scaler_path = path.replace('.faiss', '_scaler.pkl')
            import pickle
            with open(scaler_path, 'wb') as f:
                pickle.dump({
                    'scaler': self.scaler,
                    'patient_data_cache': self.patient_data_cache
                }, f)
            logger.info(f"Saved similarity index and scaler to {path}")
        except Exception as e:
            logger.error(f"Failed to save similarity index: {e}")

    def load_from_disk(self, path: str) -> bool:
        """Load FAISS index and scaler from disk."""
        try:
            if not os.path.exists(path):
                return False
            
            self.indexer.load_index(path)
            
            scaler_path = path.replace('.faiss', '_scaler.pkl')
            if os.path.exists(scaler_path):
                import pickle
                with open(scaler_path, 'rb') as f:
                    data = pickle.load(f)
                    self.scaler = data['scaler']
                    self.patient_data_cache = data['patient_data_cache']
            
            logger.info(f"Loaded similarity index from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load similarity index: {e}")
            return False

    def find_similar_patients(
        self,
        patient_features: Dict[str, Any],
        k: int = 10,
        include_outcomes: bool = False,
    ) -> Dict[str, Any]:
        """
        Find similar patients for a given patient.

        Args:
            patient_features: Feature vector for query patient
            k: Number of similar patients to return
            include_outcomes: Include treatment outcomes if available

        Returns:
            {
                'patient_id': str,
                'query_patient_age': int,
                'query_patient_conditions': [...],
                'similar_patients': [
                    {
                        'rank': 1,
                        'patient_id': str,
                        'similarity_score': float (0-1),
                        'age': int,
                        'conditions': [...],
                        'medications': [...],
                        'treatment_outcome': str or None,
                        'outcome_success_rate': float or None,
                    },
                    ...
                ],
                'model_version': str,
                'timestamp': str,
            }
        """
        try:
            if not self.indexer.get_index_stats()['ready']:
                logger.warning("FAISS index not ready")
                return {
                    'patient_id': patient_features.get('patient_id', 'unknown'),
                    'similar_patients': [],
                    'message': 'Similarity index is being rebuilt',
                }

            # Extract and scale query patient features
            query_vector = self._extract_feature_vector(patient_features)
            query_vector_scaled = self.scaler.transform([query_vector])[0]

            # Search using FAISS
            patient_id = patient_features.get('patient_id')
            result_ids, result_scores = self.indexer.search(
                query_vector_scaled.astype('float32'), 
                k=k + 1  # Get one extra in case query patient is in results
            )

            similar_patients = []
            for pid, score in zip(result_ids, result_scores):
                if pid == patient_id:
                    continue
                
                similar_patient_data = self.patient_data_cache.get(pid)
                if not similar_patient_data:
                    continue

                similar_patients.append({
                    'rank': len(similar_patients) + 1,
                    'patient_id': pid,
                    'similarity_score': float(score),
                    'age': similar_patient_data.get('age'),
                    'conditions': self._extract_conditions(similar_patient_data),
                    'medications': self._extract_medication_count(similar_patient_data),
                    'treatment_outcome': self._get_treatment_outcome(similar_patient_data),
                    'outcome_success_rate': self._estimate_success_rate(similar_patient_data),
                })

                if len(similar_patients) >= k:
                    break

            return {
                'patient_id': patient_id,
                'query_patient_age': patient_features.get('age'),
                'query_patient_conditions': self._extract_conditions(patient_features),
                'similar_patients': similar_patients[:k],
                'model_version': self.model_metadata['version'],
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error finding similar patients: {e}")
            raise

    def _extract_feature_vector(self, patient_features: Dict[str, Any]) -> np.ndarray:
        """Extract ordered feature vector for similarity calculation."""
        vector = []
        for feature_name in self.SIMILARITY_FEATURES:
            value = patient_features.get(feature_name, 0.0)
            if value is None:
                value = 0.0
            vector.append(float(value))
        return np.array(vector)

    def _extract_conditions(self, patient_data: Dict[str, Any]) -> List[str]:
        """Extract major conditions from patient data."""
        conditions = []
        for condition in ['diabetes', 'hypertension', 'heart_disease', 'kidney_disease', 'copd']:
            if patient_data.get(f'has_{condition}'):
                conditions.append(condition.replace('_', ' ').title())
        return conditions

    def _extract_medication_count(self, patient_data: Dict[str, Any]) -> int:
        """Get active medication count."""
        return patient_data.get('active_medication_count', 0)

    def _get_treatment_outcome(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the most recent treatment outcome for a patient.
        """
        outcomes = patient_data.get('outcomes', [])
        if not outcomes:
            # Fallback to encounters if outcomes list empty but we have encounter notes
            encounters = patient_data.get('encounters', [])
            for encounter in encounters:
                if encounter.get('assessment_plan'):
                    return f"Plan: {encounter['assessment_plan'][:100]}..."
            return None
        
        # Get most recent completed outcome
        latest = outcomes[0]
        if latest.get('discharge_summary'):
            return f"Discharge: {latest['discharge_summary'][:100]}..."
        if latest.get('assessment_plan'):
            return f"Assessment: {latest['assessment_plan'][:100]}..."
            
        return "Treatment completed"

    def _estimate_success_rate(self, patient_data: Dict[str, Any]) -> float:
        """
        Estimate treatment success rate based on clinical markers.
        """
        outcomes = patient_data.get('outcomes', [])
        if not outcomes:
            return 0.75  # Clinical baseline
            
        # Success proxy: completed encounters vs total, or specific keywords in notes
        completed_count = sum(1 for o in outcomes if o.get('is_completed'))
        if not outcomes:
            return 0.75
            
        base_rate = completed_count / len(outcomes)
        
        # Refine by searching for positive markers in summaries
        positive_keywords = ['improved', 'stable', 'resolved', 'recovered', 'discharged home']
        negative_keywords = ['deteriorated', 'worsened', 'referred', 'complications']
        
        scores = []
        for o in outcomes:
            text = (o.get('assessment_plan', '') + ' ' + o.get('discharge_summary', '')).lower()
            if any(k in text for k in positive_keywords):
                scores.append(0.9)
            elif any(k in text for k in negative_keywords):
                scores.append(0.3)
            else:
                scores.append(0.7)
                
        if scores:
            return sum(scores) / len(scores)
            
        return base_rate

    def compare_patients(
        self,
        patient1_features: Dict[str, Any],
        patient2_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare two patients and show differences.

        Args:
            patient1_features: Feature vector for patient 1
            patient2_features: Feature vector for patient 2

        Returns:
            {
                'patient1_id': str,
                'patient2_id': str,
                'similarity_score': float (0-1),
                'differences': [
                    {'feature': 'Age', 'patient1_value': 55, 'patient2_value': 58, 'difference': 3},
                    ...
                ],
                'similarities': [
                    {'feature': 'Hypertension', 'status': 'both_have'},
                    ...
                ],
            }
        """
        try:
            vector1 = self._extract_feature_vector(patient1_features)
            vector2 = self._extract_feature_vector(patient2_features)

            # Calculate similarity
            similarity = cosine_similarity([vector1], [vector2])[0][0]

            # Find differences
            differences = []
            similarities = []

            for i, feature_name in enumerate(self.SIMILARITY_FEATURES):
                val1 = vector1[i]
                val2 = vector2[i]

                if abs(val1 - val2) > 0.1:  # Threshold for significance
                    differences.append({
                        'feature': feature_name,
                        'patient1_value': float(val1),
                        'patient2_value': float(val2),
                        'difference': float(abs(val1 - val2)),
                    })

            # Check for same conditions
            for condition in ['diabetes', 'hypertension', 'heart_disease', 'kidney_disease']:
                p1_has = patient1_features.get(f'has_{condition}', False)
                p2_has = patient2_features.get(f'has_{condition}', False)

                if p1_has and p2_has:
                    similarities.append({
                        'feature': condition.replace('_', ' ').title(),
                        'status': 'both_have',
                    })
                elif p1_has != p2_has:
                    similarities.append({
                        'feature': condition.replace('_', ' ').title(),
                        'status': 'one_has' if p1_has else 'neither_has',
                    })

            return {
                'patient1_id': patient1_features.get('patient_id'),
                'patient2_id': patient2_features.get('patient_id'),
                'similarity_score': float(similarity),
                'differences': sorted(differences, key=lambda x: x['difference'], reverse=True),
                'similarities': similarities,
            }

        except Exception as e:
            logger.error(f"Error comparing patients: {e}")
            raise

    def batch_find_similar(
        self,
        query_patients: List[Dict[str, Any]],
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find similar patients for multiple query patients.

        Args:
            query_patients: List of feature vectors
            k: Number of similar to find for each

        Returns:
            List of similarity results
        """
        results = []
        for query_patient in query_patients:
            try:
                result = self.find_similar_patients(query_patient, k=k)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to find similar patients: {e}")
                continue

        return results


# Singleton instance
_similarity_matcher = None


def get_similarity_matcher() -> SimilarityMatcher:
    """Get or create similarity matcher singleton."""
    global _similarity_matcher
    if _similarity_matcher is None:
        _similarity_matcher = SimilarityMatcher()
    return _similarity_matcher
