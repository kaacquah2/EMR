"""API tests for AI endpoints (auth, permissions, response shape)."""

import pytest
from datetime import date
from rest_framework.test import APIClient
from core.models import User, Hospital
from patients.models import Patient
DOCTOR_AI_VIEWS_PASSWORD = "DoctorAIViewsPass1!"
NURSE_AI_VIEWS_PASSWORD = "NurseAIViewsPass1!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="AI View Test Hospital", region="Greater Accra", nhis_code="AV001")


@pytest.fixture
def doctor_user(db, hospital):
    return User.objects.create_user(
        email="doctor-views@test.com",
        password=DOCTOR_AI_VIEWS_PASSWORD,
        role="doctor",
        full_name="Dr Views",
        hospital=hospital,
    )


@pytest.fixture
def nurse_user(db, hospital):
    return User.objects.create_user(
        email="nurse-views@test.com",
        password=NURSE_AI_VIEWS_PASSWORD,
        role="nurse",
        full_name="Nurse Views",
        hospital=hospital,
    )


@pytest.fixture
def patient(db, hospital, doctor_user):
    return Patient.objects.create(
        ghana_health_id="GH-AV-001",
        full_name="View Test Patient",
        date_of_birth=date(1975, 3, 10),
        gender="female",
        registered_at=hospital,
        created_by=doctor_user,
    )


def _login(client, email, password):
    res = client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    if res.status_code != 200:
        return None
    data = res.json()
    token = data.get("access") or data.get("token")
    if token:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return token


@pytest.mark.django_db
class TestAIAnalyzePatient:
    def test_analyze_patient_requires_auth(self, api_client, patient):
        res = api_client.post(f"/api/v1/ai/analyze-patient/{patient.id}")
        assert res.status_code in (401, 403)

    def test_analyze_patient_doctor_success(self, api_client, doctor_user, patient):
        api_client.force_authenticate(user=doctor_user)
        res = api_client.post(f"/api/v1/ai/analyze-patient/{patient.id}", {}, format="json")
        assert res.status_code == 200
        data = res.json()
        assert "patient_id" in data
        assert "risk_analysis" in data
        assert "triage_assessment" in data
        assert "clinical_summary" in data
        assert "agents_executed" in data

    def test_analyze_patient_404_for_unknown(self, api_client, doctor_user):
        api_client.force_authenticate(user=doctor_user)
        res = api_client.post(
            "/api/v1/ai/analyze-patient/00000000-0000-0000-0000-000000000000",
            {},
            format="json",
        )
        assert res.status_code in (404, 400)


@pytest.mark.django_db
class TestAIRiskPrediction:
    def test_risk_prediction_returns_structure(self, api_client, doctor_user, patient):
        api_client.force_authenticate(user=doctor_user)
        res = api_client.post(f"/api/v1/ai/risk-prediction/{patient.id}", {}, format="json")
        assert res.status_code == 200
        data = res.json()
        assert "risk_predictions" in data
        assert "top_risk_disease" in data
        assert "top_risk_score" in data


@pytest.mark.django_db
class TestAITriage:
    def test_triage_returns_structure(self, api_client, nurse_user, patient):
        api_client.force_authenticate(user=nurse_user)
        res = api_client.post(
            f"/api/v1/ai/triage/{patient.id}",
            {"chief_complaint": "headache"},
            format="json",
        )
        assert res.status_code == 200
        data = res.json()
        assert data["triage_level"] in ("critical", "high", "medium", "low")
        assert "esi_level" in data
        assert "recommended_action" in data


@pytest.mark.django_db
class TestAIAnalysisHistory:
    def test_analysis_history_returns_paginated(self, api_client, doctor_user, patient):
        api_client.force_authenticate(user=doctor_user)
        res = api_client.get(f"/api/v1/ai/analysis-history/{patient.id}?limit=5&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert "analyses" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["analyses"], list)

    def test_analysis_history_404_for_unknown_patient(self, api_client, doctor_user):
        api_client.force_authenticate(user=doctor_user)
        res = api_client.get(
            "/api/v1/ai/analysis-history/00000000-0000-0000-0000-000000000000"
        )
        assert res.status_code == 404


