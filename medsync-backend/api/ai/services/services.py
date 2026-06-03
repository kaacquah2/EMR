"""
AI Services Layer - High-level service classes wrapping ML models.

Provides:
- RiskPredictionService
- DiagnosisService
- TriageService
- SimilaritySearchService
- ReferralRecommendationService

All responses include demo disclaimers and data provenance metadata.
Predictions are recorded for model performance monitoring.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal

from django.core.cache import cache
from core.models import Hospital, User, Bed, Ward, Department
from patients.models import Patient
from api.ai.data_processor import DataProcessor
from api.ai.feature_engineering import FeatureEngineer
from api.ai.ml_models import get_risk_predictor
from api.ai.clinical_validation import get_clinical_disclaimer, get_model_provenance
from api.ai.model_monitor import get_model_monitor
from api.utils import get_effective_hospital

logger = logging.getLogger(__name__)


class AIServiceException(Exception):
    """Raised when AI service encounters an error."""


class BaseAIService:
    """Base class for all AI services."""

    def __init__(self, user: User):
        """
        Initialize service with user context.

        Args:
            user: User making the request (enforces hospital scoping)
        """
        self.user = user
        self.effective_hospital = get_effective_hospital({'user': user})
        self.data_processor = DataProcessor(user)
        self.feature_engineer = FeatureEngineer()

    def _get_patient_or_raise(self, patient_id: str) -> Patient:
        """
        Get patient by ID, checking access permissions via hospital scoping.

        Uses data_processor to enforce full RBAC + hospital multi-tenancy rules.

        Raises:
            AIServiceException if patient not found or access denied
        """
        try:
            # Use data_processor which enforces:
            # - Patient exists
            # - User has hospital access to this patient
            # - User's role allows patient access
            patient = self.data_processor._get_patient_or_raise(patient_id)
            return patient
        except Patient.DoesNotExist as e:
            raise AIServiceException(f"Patient {patient_id} not found or access denied: {str(e)}")
        except Exception as e:
            raise AIServiceException(f"Error accessing patient {patient_id}: {str(e)}")

    def _extract_and_engineer_features(self, patient: Patient) -> Dict[str, Any]:
        """
        Extract patient data and engineer features.

        Returns: Feature vector ready for ML models
        """
        patient_data = self.data_processor.extract_complete_patient_data(patient)
        features = self.feature_engineer.create_feature_vector(patient_data)
        return features

    @staticmethod
    def _add_demo_metadata(result: Dict[str, Any], model_name: str = 'risk_predictor') -> Dict[str, Any]:
        """
        Add demo disclaimer and data provenance to every AI response.
        Enforces safety flags based on ModelVersion approval.
        """
        from api.models import ModelVersion
        
        # Determine clinical approval status from ModelVersion
        prod_model = ModelVersion.objects.filter(model_type=model_name, is_production=True).first()
        is_approved = prod_model.clinical_use_approved if prod_model else False
        version_tag = prod_model.version_tag if prod_model else "v1.0.0-synthetic"
        
        result['clinical_use_approved'] = is_approved
        result['model_version'] = version_tag
        result['demo_mode'] = not is_approved
        
        if not is_approved:
            result['disclaimer'] = (
                "This prediction is based on synthetic training data and must not "
                "be used for clinical decision-making."
            )
            result['clinical_validation_status'] = 'PENDING'
        else:
            result['disclaimer'] = f"Clinically validated model ({version_tag})"
            result['clinical_validation_status'] = 'APPROVED'
            
        result['data_provenance'] = get_model_provenance(model_name)
        return result

    @staticmethod
    def _record_prediction(model_name: str, features: Dict[str, Any], prediction: Dict[str, Any]) -> None:
        """
        Record a prediction for model performance monitoring.

        Non-blocking — monitoring failures never break the prediction path.
        """
        try:
            monitor = get_model_monitor()
            monitor.record_prediction(model_name, features, prediction)
        except Exception as e:
            logger.warning(f"Failed to record prediction for monitoring: {e}")


class RiskPredictionService(BaseAIService):
    """
    Disease risk prediction service.

    Predicts 5-year risk for heart disease, diabetes, stroke, pneumonia, hypertension.
    """

    CACHE_TTL = 3600  # Cache predictions for 1 hour

    def predict_risk(self, patient_id: str) -> Dict[str, Any]:
        """
        Predict disease risk for a patient.

        Args:
            patient_id: UUID of patient

        Returns:
            {
                'patient_id': str,
                'risk_predictions': {
                    'heart_disease': {'risk_score': 85.0, 'confidence': 0.92, 'risk_category': 'high'},
                    ...
                },
                'top_risk_disease': str,
                'top_risk_score': float,
                'contributing_factors': [...],
                'recommendations': [...],
                'cached': bool,
                'timestamp': str,
            }
        """
        try:
            # Check cache
            cache_key = f'risk_prediction:{patient_id}'
            cached = cache.get(cache_key)
            if cached:
                cached['cached'] = True
                return cached

            # Get patient and extract features
            patient = self._get_patient_or_raise(patient_id)
            features = self._extract_and_engineer_features(patient)

            # Run prediction
            predictor = get_risk_predictor()
            prediction = predictor.predict_risk(features)

            # MEDIUM-3: Validate confidence scores and ensure they are numeric and within [0, 100]
            confidence_scores = prediction.get("confidence_scores", {})
            for name, score in confidence_scores.items():
                if not isinstance(score, (int, float, Decimal)):
                    raise AIServiceException(f"Invalid confidence score type for {name}: {type(score)}")
                if not (0 <= float(score) <= 100):
                    raise AIServiceException(f"Confidence score out of range for {name}: {score}")

            # Add contributing factors and recommendations
            top_disease = prediction['top_risk_disease']
            contributing = predictor.get_contributing_factors(top_disease, features)

            result = {
                'patient_id': str(patient_id),
                'risk_predictions': prediction['predictions'],
                'top_risk_disease': top_disease,
                'top_risk_score': prediction['top_risk_score'],
                'contributing_factors': contributing,
                'recommendations': self._generate_recommendations(top_disease, prediction),
                'cached': False,
                'timestamp': datetime.now().isoformat(),
            }

            # Add demo metadata and provenance
            self._add_demo_metadata(result, 'risk_prediction')

            # Record for monitoring
            self._record_prediction('risk_predictor', features, result)

            # Cache result
            cache.set(cache_key, result, self.CACHE_TTL)

            logger.info(
                f"Risk prediction for patient {patient_id}: {top_disease} ({prediction['top_risk_score']:.0f}%)"
            )
            return result

        except AIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error in risk prediction: {e}")
            raise AIServiceException(f"Risk prediction failed: {str(e)}")

    def _generate_recommendations(self, disease: str, prediction: Dict) -> List[str]:
        """Generate clinical recommendations based on risk."""
        recommendations = []

        if disease == 'heart_disease' and prediction['top_risk_score'] > 60:
            recommendations.append('Consider cardiology referral')
            recommendations.append('Monitor blood pressure regularly')
            recommendations.append('Recommend stress testing')

        elif disease == 'diabetes' and prediction['top_risk_score'] > 60:
            recommendations.append('Order HbA1c and fasting glucose')
            recommendations.append('Lifestyle counseling (diet, exercise)')
            recommendations.append('Consider endocrinology referral')

        elif disease == 'stroke' and prediction['top_risk_score'] > 60:
            recommendations.append('Strict BP control')
            recommendations.append('Consider antiplatelet therapy')
            recommendations.append('Neurology consultation')

        if prediction['top_risk_score'] > 80:
            recommendations.insert(0, '⚠️ URGENT: High risk detected - expedite evaluation')

        return recommendations

    def batch_predict_risk(self, patient_ids: List[str]) -> List[Dict[str, Any]]:
        """Predict risk for multiple patients."""
        results = []
        for patient_id in patient_ids:
            try:
                result = self.predict_risk(patient_id)
                results.append(result)
            except AIServiceException as e:
                logger.error(f"Failed to predict risk for {patient_id}: {e}")
                continue
        return results


class DiagnosisService(BaseAIService):
    """
    Clinical Decision Support service for differential diagnosis.
    """

    CACHE_TTL = 1800  # Cache for 30 minutes

    def get_diagnosis_suggestions(
        self,
        patient_id: str,
        chief_complaint: Optional[str] = None,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Get differential diagnosis suggestions for a patient.

        Args:
            patient_id: UUID of patient
            chief_complaint: Chief complaint (if not in recent encounter)
            top_n: Number of suggestions to return

        Returns:
            {
                'patient_id': str,
                'chief_complaint': str,
                'diagnosis_suggestions': [
                    {
                        'rank': 1,
                        'diagnosis': 'Pneumonia',
                        'icd10_code': 'J18',
                        'probability': 0.85,
                        'confidence': 0.92,
                        'matching_symptoms': ['fever', 'cough'],
                        'recommended_tests': [...],
                        'clinical_notes': str,
                    },
                    ...
                ],
                'timestamp': str,
            }
        """
        try:
            patient = self._get_patient_or_raise(patient_id)
            features = self._extract_and_engineer_features(patient)
            if not chief_complaint:
                from api.models import Encounter
                latest_encounter = Encounter.objects.filter(
                    patient=patient,
                    hospital=self.effective_hospital
                ).order_by('-created_at').first()

                if latest_encounter:
                    chief_complaint = latest_encounter.chief_complaint or ''
                else:
                    chief_complaint = ''

            risk_result = RiskPredictionService(self.user).predict_risk(patient_id)
            top_risk = risk_result.get('top_risk_disease', 'unknown')
            suggestion_map = {
                'heart_disease': {
                    'diagnosis': 'Cardiovascular disease',
                    'icd10_code': 'I25',
                    'probability': 0.72,
                    'confidence': 0.68,
                    'matching_symptoms': ['chest pain', 'fatigue'],
                    'recommended_tests': ['ECG', 'Troponin', 'Blood pressure review'],
                    'clinical_notes': 'Risk suggestion derived from the active risk predictor.',
                },
                'diabetes': {
                    'diagnosis': 'Type 2 diabetes mellitus',
                    'icd10_code': 'E11',
                    'probability': 0.7,
                    'confidence': 0.66,
                    'matching_symptoms': ['polyuria', 'polydipsia'],
                    'recommended_tests': ['HbA1c', 'Fasting glucose'],
                    'clinical_notes': 'Risk suggestion derived from the active risk predictor.',
                },
                'stroke': {
                    'diagnosis': 'Cerebrovascular event',
                    'icd10_code': 'I63',
                    'probability': 0.68,
                    'confidence': 0.64,
                    'matching_symptoms': ['weakness', 'speech changes'],
                    'recommended_tests': ['Neurological assessment', 'CT head'],
                    'clinical_notes': 'Risk suggestion derived from the active risk predictor.',
                },
                'pneumonia': {
                    'diagnosis': 'Lower respiratory tract infection',
                    'icd10_code': 'J18',
                    'probability': 0.66,
                    'confidence': 0.62,
                    'matching_symptoms': ['fever', 'cough'],
                    'recommended_tests': ['Chest X-ray', 'Oxygen saturation'],
                    'clinical_notes': 'Risk suggestion derived from the active risk predictor.',
                },
                'hypertension': {
                    'diagnosis': 'Essential hypertension',
                    'icd10_code': 'I10',
                    'probability': 0.74,
                    'confidence': 0.7,
                    'matching_symptoms': ['headache', 'elevated blood pressure'],
                    'recommended_tests': ['Blood pressure trend review', 'Renal function'],
                    'clinical_notes': 'Risk suggestion derived from the active risk predictor.',
                },
            }
            suggestions = [{
                'rank': 1,
                **suggestion_map.get(top_risk, {
                    'diagnosis': 'General medical review',
                    'icd10_code': 'R69',
                    'probability': 0.5,
                    'confidence': 0.5,
                    'matching_symptoms': [],
                    'recommended_tests': ['Clinical review'],
                    'clinical_notes': 'No specific diagnosis suggested.',
                }),
            }]
            suggestions = suggestions[:top_n]

            result = {
                'patient_id': str(patient_id),
                'chief_complaint': chief_complaint,
                'suggestions': suggestions,
                'timestamp': datetime.now().isoformat(),
            }

            self._add_demo_metadata(result, 'risk_prediction')

            logger.info(
                f"CDS for patient {patient_id}: {suggestions[0]['diagnosis'] if suggestions else 'None'}")
            return result

        except AIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error in diagnosis service: {e}")
            raise AIServiceException(f"Diagnosis suggestion failed: {str(e)}")


class TriageService(BaseAIService):
    """
    Patient triage and emergency severity classification.
    """

    def triage_patient(
        self,
        patient_id: str,
        chief_complaint: str = '',
    ) -> Dict[str, Any]:
        """
        Triage a patient by severity.

        Args:
            patient_id: UUID of patient
            chief_complaint: Chief complaint/reason for visit

        Returns:
            {
                'patient_id': str,
                'triage_level': 'critical'|'high'|'medium'|'low',
                'triage_score': float (0-100),
                'confidence': float (0-1),
                'esi_level': int (1-5),
                'indicators': [...],
                'recommended_action': str,
                'timestamp': str,
            }
        """
        try:
            patient = self._get_patient_or_raise(patient_id)
            features = self._extract_and_engineer_features(patient)
            vitals_data = self.data_processor.extract_patient_vitals(patient, days_back=1)
            vitals = {}
            if vitals_data:
                latest_vital = vitals_data[0]
                vitals = {
                    'bp_systolic': latest_vital.get('bp_systolic'),
                    'bp_diastolic': latest_vital.get('bp_diastolic'),
                    'pulse_bpm': latest_vital.get('pulse_bpm'),
                    'spo2_percent': latest_vital.get('spo2_percent'),
                    'temperature_c': latest_vital.get('temperature_c'),
                    'resp_rate': latest_vital.get('resp_rate'),
                }

            risk_result = RiskPredictionService(self.user).predict_risk(patient_id)
            score = float(risk_result.get('top_risk_score', 0))
            indicators = []
            if vitals.get('spo2_percent') is not None and vitals['spo2_percent'] < 92:
                indicators.append('Low oxygen saturation')
                score = max(score, 85)
            if vitals.get('bp_systolic') is not None and vitals['bp_systolic'] >= 180:
                indicators.append('Severely elevated systolic blood pressure')
                score = max(score, 90)
            if vitals.get('pulse_bpm') is not None and vitals['pulse_bpm'] >= 120:
                indicators.append('Marked tachycardia')
                score = max(score, 80)

            if score >= 85:
                triage_level = 'critical'
                esi_level = 1
                action = 'Immediate emergency review'
            elif score >= 70:
                triage_level = 'high'
                esi_level = 2
                action = 'Urgent clinical review'
            elif score >= 45:
                triage_level = 'medium'
                esi_level = 3
                action = 'Assess promptly and monitor'
            else:
                triage_level = 'low'
                esi_level = 4
                action = 'Routine assessment'

            triage_result = {
                'patient_id': str(patient_id),
                'triage_level': triage_level,
                'triage_score': round(score, 1),
                'confidence': 0.68,
                'esi_level': esi_level,
                'indicators': indicators or ['Risk predictor input'],
                'recommended_action': action,
                'timestamp': datetime.now().isoformat(),
            }

            self._add_demo_metadata(triage_result, 'risk_prediction')
            logger.info(f"Triage for patient {patient_id}: {triage_level.upper()}")
            return triage_result

        except AIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error in triage service: {e}")
            raise AIServiceException(f"Triage failed: {str(e)}")


class SimilaritySearchService(BaseAIService):
    """
    Find similar patient cases for treatment benchmarking.
    """

    def find_similar_patients(
        self,
        patient_id: str,
        k: int = 10,
    ) -> Dict[str, Any]:
        """
        Find similar patients using pre-built FAISS index.
        """
        try:
            query_patient = self._get_patient_or_raise(patient_id)
            query_features = self._extract_and_engineer_features(query_patient)
            return {
                'patient_id': str(patient_id),
                'query_patient_age': query_features.get('age'),
                'similar_patients': [],
                'message': 'Similarity search is disabled in risk-only mode.',
                'model_version': 'risk-only',
                'timestamp': datetime.now().isoformat(),
            }

        except AIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error in similarity service: {e}", exc_info=True)
            raise AIServiceException(f"Similarity search failed: {str(e)}")


class ReferralRecommendationService(BaseAIService):
    """
    Smart inter-hospital referral recommendations.
    """

    def recommend_referral_hospital(
        self,
        patient_id: str,
        required_specialty: str = '',
    ) -> Dict[str, Any]:
        """
        Recommend best hospital for referral.

        Args:
            patient_id: UUID of patient
            required_specialty: Specialty needed (cardiology, orthopedics, etc.)

        Returns:
            {
                'patient_id': str,
                'recommended_hospitals': [
                    {
                        'rank': 1,
                        'hospital_name': str,
                        'hospital_id': str,
                        'specialty_match': float (0-1),
                        'bed_availability': int,
                        'distance_km': float or None,
                        'success_rate': float or None,
                        'reason': str,
                    },
                    ...
                ],
                'timestamp': str,
            }
        """
        try:
            self._get_patient_or_raise(patient_id)
            risk_result = RiskPredictionService(self.user).predict_risk(patient_id)
            top_risk = risk_result.get('top_risk_disease', 'unknown')
            risk_specialties = {
                'heart_disease': 'Cardiology',
                'diabetes': 'Endocrinology',
                'stroke': 'Neurology',
                'pneumonia': 'Pulmonology',
                'hypertension': 'Cardiology',
            }
            primary_specialty = required_specialty or risk_specialties.get(top_risk, "General")

            # Get all other active hospitals (exclude current/effective hospital).
            base_hospital = self.effective_hospital or getattr(self.user, "hospital", None)
            other_hospitals = Hospital.objects.filter(is_active=True)
            if base_hospital:
                other_hospitals = other_hospitals.exclude(id=base_hospital.id)

            recommendations: List[Dict[str, Any]] = []

            for hospital in other_hospitals:
                matching_depts = Department.objects.filter(
                    hospital=hospital,
                    name__icontains=primary_specialty,
                )

                if not matching_depts.exists():
                    continue

                available_beds = Bed.objects.filter(
                    ward__hospital=hospital,
                    status="available",
                ).count()

                recommendations.append(
                    {
                        "rank": 0,  # temporary, will set after sorting
                        "hospital_name": hospital.name,
                        "hospital_id": str(hospital.id),
                        "specialty_match": 1.0,
                        "bed_availability": available_beds,
                        "distance_km": None,
                        "success_rate": None,
                        "reason": f"Recommended for {primary_specialty or 'tertiary care'}",
                        "departments": [d.name for d in matching_depts],
                    }
                )

            # Sort and assign ranks
            recommendations.sort(key=lambda x: (x["specialty_match"], x["bed_availability"]), reverse=True)
            for idx, rec in enumerate(recommendations, start=1):
                rec["rank"] = idx

            logger.info(
                f"Referral recommendation for patient {patient_id} yielded {len(recommendations[:3])} options"
            )
            return {
                "patient_id": str(patient_id),
                "recommended_hospitals": recommendations[:3],
                "timestamp": datetime.now().isoformat(),
            }

        except AIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error in referral service: {e}")
            raise AIServiceException(f"Referral recommendation failed: {str(e)}")

    def _score_hospital_match(self, hospital: Hospital, specialty: str) -> float:
        """Score how well hospital matches specialty."""
        if not specialty:
            return 0.5

        has_exact = Department.objects.filter(
            hospital=hospital, name__icontains=specialty
        ).exists()
        return 1.0 if has_exact else 0.6

    def _estimate_bed_availability(self, hospital: Hospital) -> int:
        """Estimate available beds at hospital based on real Bed records."""
        return Bed.objects.filter(ward__hospital=hospital, status="available").count()


def get_available_beds(hospital_id: str) -> Dict[str, Any]:
    """
    MEDIUM-7: Get available beds by ward type for a hospital.

    Returns a structure suitable for driving UI and referral decisions.
    """
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        raise AIServiceException(f"Hospital {hospital_id} not found")

    bed_counts: Dict[str, int] = {}
    for ward in Ward.objects.filter(hospital=hospital, is_active=True):
        available = Bed.objects.filter(ward=ward, status="available").count()
        bed_counts[ward.ward_type] = available

    return {
        "hospital_id": str(hospital_id),
        "hospital_name": hospital.name,
        "available_beds_by_type": bed_counts,
        "total_available": sum(bed_counts.values()),
        "timestamp": datetime.now().isoformat(),
    }
