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
from sklearn.metrics.pairwise import cosine_similarity

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

    def __init__(self):
        """Initialize similarity matcher."""
        self.scaler = StandardScaler()
        self.patient_data_cache = []  # Cache of all patient feature vectors
        self.patient_features_scaled = None
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'algorithm': 'k-NN with Cosine Similarity',
            'num_features': len(self.SIMILARITY_FEATURES),
        }
        logger.info(f"Similarity matcher initialized with {len(self.SIMILARITY_FEATURES)} features")

    def index_patients(self, all_patient_features: List[Dict[str, Any]]):
        """
        Index all patients for similarity searches.

        Should be called once with all training data or periodically to update.

        Args:
            all_patient_features: List of feature vectors from FeatureEngineer
        """
        try:
            self.patient_data_cache = all_patient_features

            # Extract feature matrix
            feature_matrix = []
            for patient_data in all_patient_features:
                vector = self._extract_feature_vector(patient_data)
                feature_matrix.append(vector)

            if feature_matrix:
                # Scale features
                feature_matrix = np.array(feature_matrix)
                self.patient_features_scaled = self.scaler.fit_transform(feature_matrix)
                logger.info(f"Indexed {len(self.patient_data_cache)} patients for similarity search")
            else:
                logger.warning("No patient data to index")

        except Exception as e:
            logger.error(f"Error indexing patients: {e}")
            raise

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
            if self.patient_features_scaled is None or len(self.patient_data_cache) == 0:
                logger.warning("No indexed patients for similarity search")
                return {
                    'patient_id': patient_features.get('patient_id', 'unknown'),
                    'similar_patients': [],
                    'message': 'No patient data indexed yet',
                }

            # Extract and scale query patient features
            query_vector = self._extract_feature_vector(patient_features)
            query_vector_scaled = self.scaler.transform([query_vector])[0:1]

            # Calculate similarity with all patients
            similarities = cosine_similarity(query_vector_scaled, self.patient_features_scaled)[0]

            # Get top-k most similar (excluding self)
            patient_id = patient_features.get('patient_id')
            similar_indices = np.argsort(-similarities)  # Descending order

            similar_patients = []
            for rank, idx in enumerate(similar_indices[:k], 1):
                similar_patient_data = self.patient_data_cache[idx]
                similarity_score = float(similarities[idx])

                # Only include if not the same patient and similarity > 0.5
                if (similar_patient_data.get('patient_id') != patient_id and
                        similarity_score > 0.5):

                    similar_patients.append({
                        'rank': len(similar_patients) + 1,
                        'patient_id': similar_patient_data.get('patient_id'),
                        'similarity_score': similarity_score,
                        'age': similar_patient_data.get('age'),
                        'conditions': self._extract_conditions(similar_patient_data),
                        'medications': self._extract_medication_count(similar_patient_data),
                        'treatment_outcome': self._get_treatment_outcome(similar_patient_data),
                        'outcome_success_rate': self._estimate_success_rate(similar_patient_data),
                    })

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
        """Get treatment outcome for similar patient (if available)."""
        # TODO: Link to actual treatment outcomes from EMR
        # For now, return None
        return None

    def _estimate_success_rate(self, patient_data: Dict[str, Any]) -> Optional[float]:
        """Estimate treatment success rate for similar patient."""
        # TODO: Calculate from actual outcomes
        # For now, return None
        return None

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
