"""Unit tests for AI services (RiskPredictionService, DiagnosisService, TriageService, etc.)."""

import pytest
from datetime import date
from django.contrib.auth.hashers import make_password
from core.models import User, Hospital
from patients.models import Patient
from api.ai.services import (
    RiskPredictionService,
    DiagnosisService,
    TriageService,
    SimilaritySearchService,
    ReferralRecommendationService,
    AIServiceException,
)


def _get_test_password():
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "!@#$"
    return ''.join(secrets.choice(chars) for _ in range(12))


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="AI Test Hospital", region="Greater Accra", nhis_code="AT001")


@pytest.fixture
def doctor_user(db, hospital):
    return User.objects.create_user(
        email="doctor-ai@test.com",
        password=_get_test_password(),
        role="doctor",
        full_name="Dr AI Test",
        hospital=hospital,
    )


@pytest.fixture
def patient(db, hospital, doctor_user):
    return Patient.objects.create(
        ghana_health_id="GH-AI-TEST-001",
        full_name="AI Test Patient",
        date_of_birth=date(1980, 5, 15),
        gender="male",
        registered_at=hospital,
        created_by=doctor_user,
    )


@pytest.mark.django_db
class TestRiskPredictionService:
    def test_predict_risk_returns_structure(self, doctor_user, patient):
        service = RiskPredictionService(doctor_user)
        result = service.predict_risk(str(patient.id))
        assert 'patient_id' in result
        assert 'risk_predictions' in result
        assert 'top_risk_disease' in result
        assert 'top_risk_score' in result
        assert 'recommendations' in result
        assert result['patient_id'] == str(patient.id)
        for disease in ['heart_disease', 'diabetes', 'stroke', 'pneumonia', 'hypertension']:
            assert disease in result['risk_predictions']
            pred = result['risk_predictions'][disease]
            assert 'risk_score' in pred
            assert 'risk_category' in pred
            assert 'confidence' in pred

    def test_predict_risk_raises_for_unknown_patient(self, doctor_user):
        service = RiskPredictionService(doctor_user)
        with pytest.raises(AIServiceException):
            service.predict_risk("00000000-0000-0000-0000-000000000000")


@pytest.mark.django_db
class TestDiagnosisService:
    def test_get_diagnosis_suggestions_returns_structure(self, doctor_user, patient):
        service = DiagnosisService(doctor_user)
        result = service.get_diagnosis_suggestions(str(patient.id), chief_complaint="chest pain")
        assert 'suggestions' in result
        assert 'chief_complaint' in result
        assert isinstance(result['suggestions'], list)

    def test_get_diagnosis_suggestions_raises_for_unknown_patient(self, doctor_user):
        service = DiagnosisService(doctor_user)
        with pytest.raises(AIServiceException):
            service.get_diagnosis_suggestions("00000000-0000-0000-0000-000000000000")


@pytest.mark.django_db
class TestTriageService:
    def test_triage_patient_returns_structure(self, doctor_user, patient):
        service = TriageService(doctor_user)
        result = service.triage_patient(str(patient.id), chief_complaint="fever")
        assert 'triage_level' in result
        assert result['triage_level'] in ('critical', 'high', 'medium', 'low')
        assert 'esi_level' in result
        assert 'recommended_action' in result
        assert 'confidence' in result

    def test_triage_raises_for_unknown_patient(self, doctor_user):
        service = TriageService(doctor_user)
        with pytest.raises(AIServiceException):
            service.triage_patient("00000000-0000-0000-0000-000000000000")


@pytest.mark.django_db
class TestSimilaritySearchService:
    def test_find_similar_patients_returns_structure(self, doctor_user, patient):
        service = SimilaritySearchService(doctor_user)
        result = service.find_similar_patients(str(patient.id), k=5)
        assert 'similar_patients' in result
        assert isinstance(result['similar_patients'], list)

    def test_find_similar_raises_for_unknown_patient(self, doctor_user):
        service = SimilaritySearchService(doctor_user)
        with pytest.raises(AIServiceException):
            service.find_similar_patients("00000000-0000-0000-0000-000000000000")


@pytest.mark.django_db
class TestReferralRecommendationService:
    def test_recommend_referral_hospital_returns_structure(self, doctor_user, patient):
        service = ReferralRecommendationService(doctor_user)
        result = service.recommend_referral_hospital(str(patient.id), required_specialty="cardiology")
        assert 'recommended_hospitals' in result
        assert isinstance(result['recommended_hospitals'], list)

    def test_referral_raises_for_unknown_patient(self, doctor_user):
        service = ReferralRecommendationService(doctor_user)
        with pytest.raises(AIServiceException):
            service.recommend_referral_hospital("00000000-0000-0000-0000-000000000000")
