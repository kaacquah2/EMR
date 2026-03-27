"""
Tests for no-show override endpoint.

Tests cover:
- Successful override within 7-day window
- 403 if override window expired (>7 days)
- 400 if appointment not marked no_show
- 400 if no_show_marked_at is null (manual no-show)
- 403 if user is not doctor or hospital_admin
- Multi-hospital scoping (can't override other hospital's appointments)
- Audit logging of override action
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from core.models import Hospital, User, AuditLog
from patients.models import Patient, Appointment
import json


class NoShowOverrideTestCase(TestCase):
    """Test no-show override endpoint."""

    def setUp(self):
        """Create test fixtures."""
        self.client = APIClient()
        
        # Create two hospitals
        self.hospital1 = Hospital.objects.create(
            name="Hospital A",
            region="Region 1",
            nhis_code="H001",
            is_active=True,
        )
        
        self.hospital2 = Hospital.objects.create(
            name="Hospital B",
            region="Region 2",
            nhis_code="H002",
            is_active=True,
        )
        
        # Create users from hospital1
        self.doctor1 = User.objects.create_user(
            email="doctor1@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital1,
            account_status="active",
        )
        
        self.hospital_admin1 = User.objects.create_user(
            email="admin1@medsync.gh",
            password="SecurePass123!@#",
            role="hospital_admin",
            hospital=self.hospital1,
            account_status="active",
        )
        
        # Create nurse (should NOT have access)
        self.nurse1 = User.objects.create_user(
            email="nurse1@medsync.gh",
            password="SecurePass123!@#",
            role="nurse",
            hospital=self.hospital1,
            account_status="active",
        )
        
        # Create doctor from hospital2 (for scoping test)
        self.doctor2 = User.objects.create_user(
            email="doctor2@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital2,
            account_status="active",
        )
        
        # Create super admin (should have access)
        self.super_admin = User.objects.create_user(
            email="admin@medsync.gh",
            password="SecurePass123!@#",
            role="super_admin",
            account_status="active",
        )
        
        # Create patient in hospital1
        self.patient1 = Patient.objects.create(
            ghana_health_id="GHE001",
            full_name="Patient One",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital1,
            created_by=self.doctor1,
        )
        
        # Create patient in hospital2
        self.patient2 = Patient.objects.create(
            ghana_health_id="GHE002",
            full_name="Patient Two",
            date_of_birth="1985-05-15",
            gender="female",
            registered_at=self.hospital2,
            created_by=self.doctor2,
        )

    def test_successful_override_within_window(self):
        """Test successful override within 7-day window."""
        # Create appointment marked as no_show 1 day ago
        marked_at = timezone.now() - timedelta(days=1)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=2),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        # Doctor overrides
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Doctor approved absence - patient had emergency"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "scheduled")
        self.assertEqual(data["no_show_override_reason"], "Doctor approved absence - patient had emergency")
        
        # Verify database
        apt.refresh_from_db()
        self.assertEqual(apt.status, "scheduled")
        self.assertEqual(apt.no_show_override_reason, "Doctor approved absence - patient had emergency")

    def test_override_on_day_7_boundary(self):
        """Test override works just within 7-day boundary."""
        # Mark as no-show exactly 6.99 days ago (should still be valid)
        marked_at = timezone.now() - timedelta(days=6, hours=23, minutes=59)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=8),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Boundary test"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_override_window_expired(self):
        """Test 403 if override window expired (>7 days)."""
        # Mark as no_show 8 days ago (outside window)
        marked_at = timezone.now() - timedelta(days=8)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=9),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Too late"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        data = response.json()
        self.assertIn("override window", data["message"].lower())

    def test_appointment_not_no_show(self):
        """Test 400 if appointment not marked no_show."""
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() + timedelta(hours=2),
            status="scheduled",  # Still scheduled
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Not applicable"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("not marked as no-show", data["message"].lower())

    def test_manual_no_show_cannot_override(self):
        """Test 400 if appointment was manually marked (no_show_marked_at is null)."""
        # Manually marked no-show without timestamp
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(hours=1),
            status="no_show",
            no_show_marked_at=None,  # Manual, not auto-marked
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Cannot override manual"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("auto-marked", data["message"].lower())

    def test_nurse_cannot_override(self):
        """Test 403 if user is not doctor/hospital_admin."""
        marked_at = timezone.now() - timedelta(days=1)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=2),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.nurse1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Nurse attempt"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hospital_admin_can_override(self):
        """Test hospital_admin can override."""
        marked_at = timezone.now() - timedelta(days=2)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=3),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.hospital_admin1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Admin override"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_super_admin_can_override(self):
        """Test super_admin can override."""
        marked_at = timezone.now() - timedelta(days=2)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=3),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Super admin override"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_multi_hospital_scoping(self):
        """Test doctor cannot override other hospital's appointments."""
        # Create appointment in hospital2
        marked_at = timezone.now() - timedelta(days=1)
        apt = Appointment.objects.create(
            patient=self.patient2,
            hospital=self.hospital2,
            scheduled_at=timezone.now() - timedelta(days=2),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor2,
        )
        
        # Doctor1 tries to override (wrong hospital)
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Wrong hospital"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reason_field_required(self):
        """Test reason field is required."""
        marked_at = timezone.now() - timedelta(days=1)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=2),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": ""},  # Empty reason
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("reason", data["message"].lower())

    def test_audit_logging_on_override(self):
        """Test NO_SHOW_OVERRIDE action is logged."""
        marked_at = timezone.now() - timedelta(days=1)
        apt = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() - timedelta(days=2),
            status="no_show",
            no_show_marked_at=marked_at,
            created_by=self.doctor1,
        )
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{apt.id}/unmark-no-show",
            {"reason": "Emergency situation"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check audit log
        audit_logs = AuditLog.objects.filter(
            action="NO_SHOW_OVERRIDE",
            resource_type="appointment",
            resource_id=str(apt.id)
        )
        self.assertEqual(audit_logs.count(), 1)
        
        audit = audit_logs.first()
        self.assertEqual(audit.user, self.doctor1)
        self.assertEqual(audit.hospital, self.hospital1)

    def test_appointment_not_found(self):
        """Test 404 if appointment doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        self.client.force_authenticate(user=self.doctor1)
        response = self.client.post(
            f"/api/v1/appointments/{fake_id}/unmark-no-show",
            {"reason": "Non-existent"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
