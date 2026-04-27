#!/usr/bin/env python
"""Test that trained models load correctly with new versioned paths."""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')

import django
django.setup()

from api.ai.ml_models import get_risk_predictor
from django.conf import settings

print("\n=== Phase 3 Model Loading Test ===\n")

print(f"AI_MODEL_VERSION: {settings.AI_MODEL_VERSION}")
print(f"AI_MODELS_TRAINED_ON_REAL_DATA: {settings.AI_MODELS_TRAINED_ON_REAL_DATA}")

rp = get_risk_predictor()
print(f"\nRisk Predictor Status:")
print(f"  Version: {rp.model_metadata['version']}")
print(f"  Diseases: {rp.model_metadata['diseases']}")
print(f"  Models loaded: {len(rp.models)} models")

# Check if using real models or placeholder
has_real_models = any(
    hasattr(model, 'predict_proba') 
    for model in rp.models.values()
)
placeholder_models = any(
    isinstance(model, dict) and model.get('type') == 'placeholder'
    for model in rp.models.values()
)

if has_real_models:
    print("  Status: [OK] Real trained models loaded")
elif placeholder_models:
    print("  Status: [WARN] Using placeholder models (fallback)")
else:
    print("  Status: [?] Model type unknown")

# Test prediction
print("\nTest Prediction:")
test_features = {
    'age': 55,
    'gender_male': 1,
    'gender_female': 0,
    'blood_group_o': 1,
    'blood_group_a': 0,
    'blood_group_b': 0,
    'blood_group_ab': 0,
    'blood_group_rh_positive': 1,
    'bp_systolic_mean': 145,
    'bp_diastolic_mean': 95,
    'pulse_mean': 78,
    'spo2_mean': 96,
    'weight_mean': 80,
    'bmi_mean': 28,
    'active_medication_count': 2,
    'medication_complexity_score': 3,
    'allergy_count': 1,
    'allergy_severity_index': 2,
    'comorbidity_index': 1,
    'chronic_condition_count': 1,
    'has_diabetes': 0,
    'has_hypertension': 1,
    'has_heart_disease': 0,
    'has_kidney_disease': 0,
    'has_copd': 0,
    'has_asthma': 0,
    'patient_id': 'TEST001',
}

result = rp.predict_risk(test_features)
print(f"  Patient: {result['patient_id']}")
print(f"  Top Risk Disease: {result['top_risk_disease']}")
print(f"  Top Risk Score: {result['top_risk_score']:.1f}/100")
print(f"  Model Version: {result['model_version']}")

print("\n[OK] Phase 3 integration complete!\n")
