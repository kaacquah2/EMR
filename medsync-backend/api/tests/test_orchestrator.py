"""Tests for AI multi-agent orchestrator."""

import pytest
from api.ai.agents import get_orchestrator
from api.ai.agents.orchestrator import AIOrchestrator


@pytest.fixture
def sample_patient_data():
    """Minimal patient data shape expected by orchestrator."""
    return {
        "demographics": {
            "patient_id": "test-patient-001",
            "age": 55,
            "gender": "male",
            "blood_group": "O+",
        },
        "diagnoses": [],
        "medications": [],
        "allergies": [],
        "vitals": [
            {
                "bp_systolic": 130,
                "bp_diastolic": 85,
                "pulse_bpm": 78,
                "spo2_percent": 98,
                "temperature_c": 36.8,
            }
        ],
        "labs": [],
        "admissions": [],
        "encounters": [],
    }


@pytest.fixture
def sample_features():
    """Minimal feature vector from FeatureEngineer."""
    return {
        "patient_id": "test-patient-001",
        "age": 55,
        "gender_male": 1,
        "gender_female": 0,
        "bp_systolic_mean": 130,
        "bp_diastolic_mean": 85,
        "pulse_mean": 78,
        "spo2_mean": 98,
        "bmi_mean": 25,
        "active_medication_count": 0,
        "comorbidity_index": 0,
        "has_diabetes": 0,
        "has_hypertension": 0,
        "has_heart_disease": 0,
    }


class TestAIOrchestrator:
    def test_get_orchestrator_returns_singleton(self):
        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2
        assert isinstance(o1, AIOrchestrator)

    def test_analyze_patient_comprehensive_returns_full_structure(
        self, sample_patient_data, sample_features
    ):
        orchestrator = get_orchestrator()
        result = orchestrator.analyze_patient_comprehensive(
            sample_patient_data,
            sample_features,
            chief_complaint="chest pain",
            include_similarity=False,
            include_referral=False,
        )
        assert "patient_id" in result
        assert "analysis_timestamp" in result
        assert "agents_executed" in result
        assert "risk_analysis" in result
        assert "triage_assessment" in result
        assert "diagnosis_suggestions" in result
        assert "clinical_summary" in result
        assert "recommended_actions" in result
        assert "alerts" in result
        assert "confidence_score" in result
        assert "data_agent" in result["agents_executed"]
        assert "prediction_agent" in result["agents_executed"]
        assert "triage_agent" in result["agents_executed"]
        assert "diagnosis_agent" in result["agents_executed"]
        assert "summary_agent" in result["agents_executed"]

    def test_analyze_patient_with_similarity_and_referral(
        self, sample_patient_data, sample_features
    ):
        orchestrator = get_orchestrator()
        result = orchestrator.analyze_patient_comprehensive(
            sample_patient_data,
            sample_features,
            chief_complaint="fever",
            include_similarity=True,
            include_referral=True,
        )
        assert "similarity_agent" in result["agents_executed"] or "similar_patients" in result
        assert "referral_agent" in result["agents_executed"] or "referral_recommendations" in result
