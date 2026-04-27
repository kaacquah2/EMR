"""
PHASE 7.4: Receptionist Walk-in Queue Tests

Tests for walk-in appointment creation and queue management endpoints.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Hospital, User
from patients.models import Patient, Appointment


@pytest.fixture
def hospital():
    """Create test hospital."""
    return Hospital.objects.create(
        name="Test Hospital",
        code="TEST001",is_active=True,
    )


@pytest.fixture
def receptionist(hospital):
    """Create receptionist user."""
    return User.objects.create_user(
        email="receptionist@test.local",
        password="testpass123",
        first_name="Rec",
        last_name="Eptionist",
        role="receptionist",
        hospital=hospital,
        account_status="active",
    )


@pytest.fixture
def doctor(hospital):
    """Create doctor user."""
    user = User.objects.create_user(
        email="doctor@test.local",
        password="testpass123",
        first_name="Doc",
        last_name="Tor",
        role="doctor",
        hospital=hospital,
        account_status="active",
    )
    return user


@pytest.fixture
def nurse(hospital):
    """Create nurse user."""
    return User.objects.create_user(
        email="nurse@test.local",
        password="testpass123",
        first_name="Nur",
        last_name="Sed",
        role="nurse",
        hospital=hospital,
        account_status="active",
    )


@pytest.fixture
def patient(hospital):
    """Create test patient."""
    return Patient.objects.create(
        ghana_health_id="GHN123456789",
        full_name="John Doe",
        date_of_birth="1990-01-01",
        gender="male",
        blood_group="O+",
        registered_at=hospital,
        created_by=User.objects.create_user(
            email="admin@test.local",
            password="testpass123",
            role="hospital_admin",
            hospital=hospital,
        ),
    )


@pytest.mark.django_db
class TestWalkInQueue:
    """Test walk-in appointment creation and queue management."""

    def test_create_walk_in_as_receptionist(self, receptionist, patient, hospital):
        """Receptionist can create walk-in appointments."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": str(patient.id),
            "reason": "Fever and cough",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "checked_in"
        assert response.data["urgency"] == "routine"
        assert response.data["queue_position"] == 1
        assert response.data["patient_id"] == str(patient.id)
        
        # Verify appointment was created
        apt = Appointment.objects.get(id=response.data["id"])
        assert apt.appointment_type == "walk_in"
        assert apt.status == "checked_in"
        assert apt.urgency == "routine"
        assert apt.reason == "Fever and cough"

    def test_create_walk_in_as_nurse(self, nurse, patient, hospital):
        """Nurse can create walk-in appointments."""
        client = APIClient()
        client.force_authenticate(user=nurse)
        
        payload = {
            "patient_id": str(patient.id),
            "reason": "Blood pressure check",
            "urgency": "urgent",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["urgency"] == "urgent"

    def test_create_walk_in_with_doctor(self, receptionist, patient, doctor, hospital):
        """Can assign doctor to walk-in appointment."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": str(patient.id),
            "doctor_id": str(doctor.id),
            "reason": "Consultation",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["doctor"] == doctor.get_full_name()

    def test_create_walk_in_unassigned_doctor(self, receptionist, patient, hospital):
        """Walk-in without assigned doctor shows 'Unassigned'."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": str(patient.id),
            "reason": "Walk-in",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["doctor"] == "Unassigned"

    def test_create_walk_in_invalid_urgency(self, receptionist, patient, hospital):
        """Invalid urgency defaults to 'routine'."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": str(patient.id),
            "reason": "Walk-in",
            "urgency": "invalid",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["urgency"] == "routine"

    def test_create_walk_in_missing_patient(self, receptionist, hospital):
        """Missing patient_id returns 400."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "reason": "Walk-in",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "patient_id required" in response.data["message"]

    def test_create_walk_in_invalid_patient(self, receptionist, hospital):
        """Invalid patient_id returns 404."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": "00000000-0000-0000-0000-000000000000",
            "reason": "Walk-in",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_walk_in_invalid_doctor(self, receptionist, patient, hospital):
        """Invalid doctor_id returns 404."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        payload = {
            "patient_id": str(patient.id),
            "doctor_id": "00000000-0000-0000-0000-000000000000",
            "reason": "Walk-in",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_walk_in_permission_denied(self, patient, hospital):
        """Non-authorized roles cannot create walk-in."""
        # Create a doctor user (not authorized for walk-in creation)
        doctor = User.objects.create_user(
            email="doctor2@test.local",
            password="testpass123",
            role="doctor",
            hospital=hospital,
        )
        
        client = APIClient()
        client.force_authenticate(user=doctor)
        
        payload = {
            "patient_id": str(patient.id),
            "reason": "Walk-in",
            "urgency": "routine",
        }
        
        response = client.post("/api/appointments/walk-in", payload, format="json")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_walk_in_queue_today(self, receptionist, patient, hospital):
        """Get walk-in queue for today."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create multiple walk-ins
        for i in range(3):
            Appointment.objects.create(
                patient=patient,
                hospital=hospital,
                scheduled_at=timezone.now(),
                appointment_type="walk_in",
                status="checked_in",
                urgency="routine" if i < 2 else "urgent",
                queue_position=i + 1,
                created_by=receptionist,
            )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_waiting"] == 3
        assert response.data["urgent_count"] == 1
        assert response.data["emergency_count"] == 0
        assert len(response.data["queue"]) == 3

    def test_walk_in_queue_by_date(self, receptionist, patient, hospital):
        """Get walk-in queue for specific date."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create walk-in for today
        Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="routine",
            queue_position=1,
            created_by=receptionist,
        )
        
        # Query for yesterday (should be empty)
        yesterday = (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%d")
        response = client.get(f"/api/appointments/walk-in-queue?date={yesterday}")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_waiting"] == 0
        assert response.data["queue"] == []

    def test_walk_in_queue_excludes_completed(self, receptionist, patient, hospital):
        """Walk-in queue excludes completed appointments."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create checked-in walk-in
        checked_in = Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="routine",
            queue_position=1,
            created_by=receptionist,
        )
        
        # Create completed walk-in
        completed = Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="completed",
            urgency="routine",
            queue_position=2,
            created_by=receptionist,
        )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_waiting"] == 1
        assert response.data["queue"][0]["id"] == str(checked_in.id)

    def test_walk_in_queue_ordered_by_urgency(self, receptionist, patient, hospital):
        """Walk-in queue orders by urgency then queue position."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create walk-ins in different order
        appt1 = Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="routine",
            queue_position=1,
            created_by=receptionist,
        )
        
        appt2 = Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="emergency",
            queue_position=2,
            created_by=receptionist,
        )
        
        appt3 = Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="urgent",
            queue_position=3,
            created_by=receptionist,
        )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["queue"]) == 3
        # Emergency should be first (queue_number 1)
        assert response.data["queue"][0]["id"] == str(appt2.id)
        assert response.data["queue"][0]["queue_number"] == 1
        # Urgent should be second (queue_number 2)
        assert response.data["queue"][1]["id"] == str(appt3.id)
        assert response.data["queue"][1]["queue_number"] == 2
        # Routine should be third (queue_number 3)
        assert response.data["queue"][2]["id"] == str(appt1.id)
        assert response.data["queue"][2]["queue_number"] == 3

    def test_walk_in_queue_permission_doctor(self, doctor, patient, hospital):
        """Doctors can view walk-in queue."""
        client = APIClient()
        client.force_authenticate(user=doctor)
        
        # Create a walk-in
        Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="routine",
            queue_position=1,
            created_by=doctor,
        )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK

    def test_walk_in_queue_invalid_date_format(self, receptionist, hospital):
        """Invalid date format returns 400."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        response = client.get("/api/appointments/walk-in-queue?date=invalid-date")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid date format" in response.data["message"]

    def test_walk_in_queue_wait_time(self, receptionist, patient, hospital):
        """Queue includes wait time in minutes."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create walk-in
        Appointment.objects.create(
            patient=patient,
            hospital=hospital,
            scheduled_at=timezone.now(),
            appointment_type="walk_in",
            status="checked_in",
            urgency="routine",
            queue_position=1,
            created_by=receptionist,
        )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK
        assert "wait_time_minutes" in response.data["queue"][0]
        assert response.data["queue"][0]["wait_time_minutes"] >= 0

    def test_walk_in_queue_pagination_counts(self, receptionist, patient, hospital):
        """Queue includes emergency and urgent counts."""
        client = APIClient()
        client.force_authenticate(user=receptionist)
        
        # Create varied urgency walk-ins
        for urgency in ["emergency", "emergency", "urgent", "routine", "routine", "routine"]:
            Appointment.objects.create(
                patient=patient,
                hospital=hospital,
                scheduled_at=timezone.now(),
                appointment_type="walk_in",
                status="checked_in",
                urgency=urgency,
                queue_position=None,
                created_by=receptionist,
            )
        
        response = client.get("/api/appointments/walk-in-queue")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["emergency_count"] == 2
        assert response.data["urgent_count"] == 1
        assert response.data["total_waiting"] == 6


