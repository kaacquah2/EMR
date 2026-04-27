"""
Disease Risk Prediction Model.

Predicts 5-year risk for:
- Heart Disease
- Diabetes
- Stroke
- Pneumonia
- Hypertension

Uses XGBoost for high accuracy and interpretability.
"""

import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskPredictorModel:
    """
    XGBoost-based disease risk prediction model.
    """

    # Disease names
    DISEASES = [
        'heart_disease',
        'diabetes',
        'stroke',
        'pneumonia',
        'hypertension',
    ]

    # Feature names expected by the model
    REQUIRED_FEATURES = [
        'age',
        'gender_male',
        'gender_female',
        'blood_group_o',
        'blood_group_a',
        'blood_group_b',
        'blood_group_ab',
        'blood_group_rh_positive',
        'bp_systolic_mean',
        'bp_diastolic_mean',
        'pulse_mean',
        'spo2_mean',
        'weight_mean',
        'bmi_mean',
        'active_medication_count',
        'medication_complexity_score',
        'allergy_count',
        'allergy_severity_index',
        'comorbidity_index',
        'chronic_condition_count',
        'has_diabetes',
        'has_hypertension',
        'has_heart_disease',
        'has_kidney_disease',
        'has_copd',
        'has_asthma',
    ]

    def __init__(self):
        """Initialize risk predictor. Loads from api/ai/models/risk_predictor.joblib if present."""
        self.models = {}  # Dict[disease, xgb.Booster or mock]
        self._feature_order = list(self.REQUIRED_FEATURES)
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'algorithm': 'XGBoost',
            'diseases': self.DISEASES,
        }
        if not self._load_models_from_disk():
            self._create_placeholder_models()

    def _load_models_from_disk(self) -> bool:
        """Load trained models from versioned directory or fallback to single files. Returns True if loaded."""
        try:
            import joblib
        except ImportError:
            logger.warning("joblib not installed; cannot load risk predictor from disk")
            return False
        try:
            from api.ai.model_config import get_models_dir
            from django.conf import settings
            
            models_dir = get_models_dir()
            
            # Phase 3: Try to load from versioned model directory first
            # Version comes from settings.AI_MODEL_VERSION (e.g., "1.0.0-hybrid")
            model_version = getattr(settings, 'AI_MODEL_VERSION', '1.0.0-hybrid')
            versioned_dir = models_dir / f"v{model_version}"
            
            # Check versioned directory first (Phase 3 trained models)
            if versioned_dir.exists():
                risk_predictor_file = versioned_dir / 'risk_predictor.joblib'
                if risk_predictor_file.exists():
                    payload = joblib.load(risk_predictor_file)
                    self.models = payload.get('models', {})
                    if payload.get('feature_order'):
                        self._feature_order = list(payload['feature_order'])
                    if payload.get('version'):
                        self.model_metadata['version'] = payload['version']
                    logger.info("Loaded risk predictor from versioned models (v%s)", model_version)
                    return bool(self.models)
            
            # Fallback: Try single file (legacy format)
            legacy_path = models_dir / 'risk_predictor.joblib'
            if legacy_path.exists():
                payload = joblib.load(legacy_path)
                self.models = payload.get('models', {})
                if payload.get('feature_order'):
                    self._feature_order = list(payload['feature_order'])
                if payload.get('version'):
                    self.model_metadata['version'] = payload['version']
                logger.info("Loaded risk predictor from legacy single file")
                return bool(self.models)
            
            # No models found
            logger.warning("No risk predictor models found in %s or v%s/", models_dir, model_version)
            return False
        except Exception as e:
            logger.warning("Could not load risk predictor from disk: %s", e)
            return False

    def _create_placeholder_models(self):
        """
        Create placeholder models for demo/testing.

        In production, these will be loaded from trained .joblib files.
        """
        for disease in self.DISEASES:
            self.models[disease] = {
                'type': 'placeholder',
                'algorithm': 'XGBoost',
                'disease': disease,
                'feature_count': len(self.REQUIRED_FEATURES),
            }
            logger.info(f"Created placeholder model for {disease}")

    def predict_risk(
        self,
        features: Dict[str, Any],
        return_confidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict disease risk for a patient.

        Args:
            features: Feature vector from FeatureEngineer (patient profile)
            return_confidence: Include confidence intervals

        Returns:
            {
                'patient_id': str,
                'predictions': {
                    'heart_disease': {
                        'risk_score': float (0-100),
                        'confidence': float (0-1),
                        'risk_category': 'low'|'medium'|'high'|'critical',
                    },
                    'diabetes': {...},
                    ...
                },
                'top_risk_disease': str,
                'top_risk_score': float,
                'model_version': str,
                'timestamp': str,
            }
        """
        try:
            patient_id = features.get('patient_id', 'unknown')
            predictions = {}

            # Extract feature vector in model's expected order
            feature_vector = self._prepare_feature_vector(features)

            # Get predictions for each disease
            for disease in self.DISEASES:
                risk_score, confidence = self._predict_disease_risk(
                    disease,
                    feature_vector,
                    features
                )

                risk_category = self._categorize_risk(risk_score)

                predictions[disease] = {
                    'risk_score': float(risk_score),
                    'confidence': float(confidence),
                    'risk_category': risk_category,
                }

            # Find highest risk
            top_disease = max(predictions.items(), key=lambda x: x[1]['risk_score'])

            return {
                'patient_id': patient_id,
                'predictions': predictions,
                'top_risk_disease': top_disease[0],
                'top_risk_score': top_disease[1]['risk_score'],
                'model_version': self.model_metadata['version'],
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error predicting risk for patient {features.get('patient_id')}: {e}")
            raise

    def _prepare_feature_vector(self, features: Dict[str, Any]) -> List[List[float]]:
        """
        Extract and order features for the model.

        Returns: 2D row vector (sklearn/xgboost accept nested lists; avoids numpy import at module load).
        """
        feature_vector: List[float] = []

        for feature_name in self._feature_order:
            value = features.get(feature_name)

            # Handle missing values
            if value is None:
                value = 0.0
            elif isinstance(value, (int, float)):
                value = float(value)
            else:
                value = 0.0

            feature_vector.append(value)

        return [feature_vector]

    def _predict_disease_risk(
        self,
        disease: str,
        feature_vector: List[List[float]],
        features: Dict[str, Any],
    ) -> Tuple[float, float]:
        """
        Predict risk score and confidence for a disease.

        Args:
            disease: Disease name
            feature_vector: Prepared 2D feature row (one sample)
            features: Raw features (for rule-based fallback)

        Returns:
            (risk_score: 0-100, confidence: 0-1)
        """

        # If model is placeholder, use rule-based scoring
        if isinstance(self.models.get(disease), dict) and self.models[disease].get('type') == 'placeholder':
            return self._rule_based_risk_score(disease, features)

        model = self.models.get(disease)
        if model is not None and hasattr(model, 'predict_proba'):
            try:
                proba = model.predict_proba(feature_vector)[0]
                prob = float(proba[1]) if proba.size > 1 else float(proba[0])
                score = min(100.0, max(0.0, prob * 100.0))
                confidence = 0.85
                return (score, confidence)
            except Exception as e:
                logger.warning("Model prediction failed for %s: %s", disease, e)
        return self._rule_based_risk_score(disease, features)

    def _rule_based_risk_score(
        self,
        disease: str,
        features: Dict[str, Any],
    ) -> Tuple[float, float]:
        """
        Fallback rule-based risk scoring (until ML models trained).

        This provides sensible default predictions based on known risk factors.
        """

        score = 0.0

        if disease == 'heart_disease':
            # Age factor
            age = features.get('age', 50)
            score += (age - 30) / 2  # +1% per year over 30

            # BP factor
            bp_sys = features.get('bp_systolic_mean', 120)
            if bp_sys > 140:
                score += 20
            elif bp_sys > 130:
                score += 10

            # Existing condition
            if features.get('has_heart_disease'):
                score += 50
            if features.get('has_hypertension'):
                score += 15
            if features.get('has_diabetes'):
                score += 15

            # Weight/BMI
            bmi = features.get('bmi_mean')
            if bmi and bmi > 30:
                score += 10

            score = min(95, score)  # Cap at 95%

        elif disease == 'diabetes':
            age = features.get('age', 50)
            score += (age - 25) / 3

            # Existing diabetes
            if features.get('has_diabetes'):
                score += 70

            # BMI
            bmi = features.get('bmi_mean')
            if bmi and bmi > 35:
                score += 25
            elif bmi and bmi > 30:
                score += 15

            # Hypertension
            if features.get('has_hypertension'):
                score += 10

            score = min(95, score)

        elif disease == 'stroke':
            age = features.get('age', 50)
            score += (age - 30) / 1.5

            # High BP
            bp_sys = features.get('bp_systolic_mean', 120)
            if bp_sys > 160:
                score += 40
            elif bp_sys > 140:
                score += 25

            if features.get('has_heart_disease'):
                score += 20
            if features.get('has_diabetes'):
                score += 15

            score = min(95, score)

        elif disease == 'pneumonia':
            # Recent admission increases risk
            recent_admission = features.get('recent_admission_count', 0)
            score += recent_admission * 20

            # Age extremes
            age = features.get('age', 50)
            if age < 5 or age > 65:
                score += 15

            # Low oxygen
            spo2 = features.get('spo2_mean', 98)
            if spo2 < 92:
                score += 25

            # Chronic conditions increase risk
            chronic_count = features.get('chronic_condition_count', 0)
            score += chronic_count * 10

            score = min(85, score)  # Lower baseline for pneumonia

        elif disease == 'hypertension':
            # Age factor
            age = features.get('age', 50)
            score += (age - 30) / 2

            # Current BP
            bp_sys = features.get('bp_systolic_mean', 120)
            if bp_sys > 140:
                score += 50
            elif bp_sys > 130:
                score += 30

            # Family history proxy (existing HTN meds)
            if features.get('has_hypertension'):
                score += 60

            # BMI
            bmi = features.get('bmi_mean')
            if bmi and bmi > 30:
                score += 15

            score = min(95, score)

        else:
            score = 25.0  # Default baseline

        # Confidence depends on feature completeness
        feature_completeness = self._calculate_feature_completeness(features)
        confidence = 0.65 + (feature_completeness * 0.25)  # 0.65-0.90

        return max(0.0, min(100.0, score)), confidence

    def _categorize_risk(self, risk_score: float) -> str:
        """
        Categorize risk score into levels.

        Args:
            risk_score: 0-100

        Returns: 'low', 'medium', 'high', or 'critical'
        """
        if risk_score < 20:
            return 'low'
        elif risk_score < 50:
            return 'medium'
        elif risk_score < 80:
            return 'high'
        else:
            return 'critical'

    def _calculate_feature_completeness(self, features: Dict[str, Any]) -> float:
        """
        Calculate feature completeness (0-1).

        How many of the required features are provided (not None/0)?
        """
        provided_count = sum(
            1 for feature in self.REQUIRED_FEATURES
            if feature in features and features[feature] is not None
        )
        return provided_count / len(self.REQUIRED_FEATURES)

    def get_contributing_factors(
        self,
        disease: str,
        features: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Explain which factors contributed to the risk score.

        Returns:
            [
                {'factor': 'High Blood Pressure', 'weight': 'high', 'value': '145 mmHg'},
                {'factor': 'Age 55', 'weight': 'medium', 'value': '55 years'},
                ...
            ]
        """

        factors = []

        if disease == 'heart_disease':
            bp_sys = features.get('bp_systolic_mean')
            if bp_sys and bp_sys > 140:
                factors.append({
                    'factor': 'Elevated Blood Pressure',
                    'weight': 'high',
                    'value': f'{bp_sys:.0f} mmHg',
                })

            if features.get('has_hypertension'):
                factors.append({
                    'factor': 'Existing Hypertension Diagnosis',
                    'weight': 'high',
                    'value': 'Diagnosed',
                })

            age = features.get('age', 0)
            if age > 55:
                factors.append({
                    'factor': 'Age',
                    'weight': 'medium',
                    'value': f'{age} years',
                })

        elif disease == 'diabetes':
            bmi = features.get('bmi_mean')
            if bmi and bmi > 30:
                factors.append({
                    'factor': 'Overweight/Obese',
                    'weight': 'high',
                    'value': f'BMI {bmi:.1f}',
                })

            if features.get('has_hypertension'):
                factors.append({
                    'factor': 'Hypertension',
                    'weight': 'medium',
                    'value': 'Diagnosed',
                })

        elif disease == 'stroke':
            bp_sys = features.get('bp_systolic_mean')
            if bp_sys and bp_sys > 160:
                factors.append({
                    'factor': 'Very High Blood Pressure',
                    'weight': 'critical',
                    'value': f'{bp_sys:.0f} mmHg',
                })

            age = features.get('age', 0)
            if age > 65:
                factors.append({
                    'factor': 'Advanced Age',
                    'weight': 'medium',
                    'value': f'{age} years',
                })

        return factors

    def batch_predict(
        self,
        feature_list: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run predictions for multiple patients.

        Args:
            feature_list: List of feature vectors from FeatureEngineer

        Returns:
            List of prediction results
        """
        results = []
        for features in feature_list:
            try:
                result = self.predict_risk(features)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to predict for patient: {e}")
                continue

        return results


# Singleton instance
_risk_predictor = None


def get_risk_predictor() -> RiskPredictorModel:
    """Get or create risk predictor singleton."""
    global _risk_predictor
    if _risk_predictor is None:
        _risk_predictor = RiskPredictorModel()
    return _risk_predictor
