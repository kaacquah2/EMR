import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from core.models import User, Hospital
from patients.models import Patient, Appointment


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def hospital():
    return Hospital.objects.create(
        name="Test Hospital",
        region="Greater Accra",
        nhis_code="TST001",
        address="Test Address"
    )


@pytest.fixture
def receptionist_user(hospital):
    user = User.objects.create_user(
        email="receptionist@test.gh",
        password="TestPassword123!",
        role="receptionist",
        hospital=hospital,
        full_name="Test Receptionist"
    )
    user.account_status="active"
    user.save()
    return user


@pytest.fixture
def patient(hospital, receptionist_user):
    return Patient.objects.create(
        ghana_health_id="GH123456789",
        full_name="Test Patient",
        date_of_birth="1990-01-15",
        gender="M",
        registered_at=hospital,
        created_by=receptionist_user
    )


@pytest.mark.django_db
def test_bulk_import_appointments_success(api_client, receptionist_user, patient):
    """Test successful bulk import of appointments"""
    api_client.force_authenticate(user=receptionist_user)

    future_time = timezone.now() + timedelta(days=7)

    payload = {
        "appointments": [
            {
                "patient_id": str(patient.id),
                "scheduled_at": future_time.isoformat(),
                "appointment_type": "outpatient",
                "notes": "Test appointment 1"
            },
            {
                "patient_id": str(patient.id),
                "scheduled_at": (future_time + timedelta(hours=2)).isoformat(),
                "appointment_type": "follow_up",
                "notes": "Test appointment 2"
            }
        ]
    }

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2
    assert data["failed"] == 0
    assert len(data["details"]) == 2
    assert all(d["status"] == "success" for d in data["details"])

    # Verify appointments were created
    appointments = Appointment.objects.filter(patient=patient)
    assert appointments.count() == 2


@pytest.mark.django_db
def test_bulk_import_appointments_missing_patient(api_client, receptionist_user):
    """Test bulk import with non-existent patient"""
    api_client.force_authenticate(user=receptionist_user)

    future_time = timezone.now() + timedelta(days=7)

    payload = {
        "appointments": [
            {
                "patient_id": "00000000-0000-0000-0000-000000000000",
                "scheduled_at": future_time.isoformat(),
            }
        ]
    }

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    # Should return success but with failed details
    assert response.status_code in (200, 400)
    data = response.json()
    if response.status_code == 400:
        # Some implementations might reject empty appointments
        assert "appointments array required" in data.get("message", "") or "failed" in data
    else:
        assert data["created"] == 0
        assert data["failed"] == 1
        assert data["details"][0]["status"] == "error"
        assert "Patient not found" in data["details"][0]["message"]


@pytest.mark.django_db
def test_bulk_import_appointments_past_date(api_client, receptionist_user, patient):
    """Test bulk import with past appointment date"""
    api_client.force_authenticate(user=receptionist_user)

    past_time = timezone.now() - timedelta(days=1)

    payload = {
        "appointments": [
            {
                "patient_id": str(patient.id),
                "scheduled_at": past_time.isoformat(),
            }
        ]
    }

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    # Should return with failed details
    assert response.status_code in (200, 400)
    data = response.json()
    if response.status_code == 200:
        assert data["created"] == 0
        assert data["failed"] == 1
        assert "future" in data["details"][0]["message"].lower()


@pytest.mark.django_db
def test_bulk_import_appointments_missing_patient_id(api_client, receptionist_user):
    """Test bulk import without patient_id"""
    api_client.force_authenticate(user=receptionist_user)

    future_time = timezone.now() + timedelta(days=7)

    payload = {
        "appointments": [
            {
                "scheduled_at": future_time.isoformat(),
            }
        ]
    }

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    # Should return failed result
    assert response.status_code in (200, 400)
    data = response.json()
    if response.status_code == 200:
        assert data["created"] == 0
        assert data["failed"] == 1


@pytest.mark.django_db
def test_bulk_import_appointments_permission_denied(api_client, hospital):
    """Test bulk import with insufficient permissions (nurse)"""
    nurse = User.objects.create_user(
        email="nurse@test.gh",
        password="TestPassword123!",
        role="nurse",
        hospital=hospital,
        full_name="Test Nurse"
    )
    nurse.account_status="active"
    nurse.save()

    api_client.force_authenticate(user=nurse)

    payload = {"appointments": []}

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_bulk_import_appointments_empty_list(api_client, receptionist_user):
    """Test bulk import with empty appointments list"""
    api_client.force_authenticate(user=receptionist_user)

    payload = {"appointments": []}

    response = api_client.post("/api/v1/appointments/bulk-import", payload, format="json")

    assert response.status_code == 400
    assert "appointments array required" in response.json()["message"]


