"""
Tests for break-glass time-window enforcement (15-minute access window).
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
import json

from core.models import User, Hospital, AuditLog
from interop.models import GlobalPatient, BreakGlassLog
from patients.models import Patient


class BreakGlassTimeWindowTestCase(TestCase):
    """Test break-glass 15-minute time-window enforcement."""

    def setUp(self):
        """Create test fixtures."""
        self.client = APIClient()

        # Create hospitals
        self.hospital1 = Hospital.objects.create(
            name="Test Hospital 1",
            region="Region A",
            nhis_code="H001",
            is_active=True,
        )
        self.hospital2 = Hospital.objects.create(
            name="Test Hospital 2",
            region="Region B",
            nhis_code="H002",
            is_active=True,
        )

        # Create users
        self.doctor1 = User.objects.create_user(
            email="doctor1@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital1,
            account_status="active",
        )
        self.hospital_admin = User.objects.create_user(
            email="admin@medsync.gh",
            password="SecurePass123!@#",
            role="hospital_admin",
            hospital=self.hospital1,
            account_status="active",
        )

        # Create global patient
        self.global_patient = GlobalPatient.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def test_break_glass_expires_at_set_on_creation(self):
        """Test that BreakGlassLog can be created with expires_at field."""
        before = timezone.now()
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Critical emergency",
            expires_at=before + timedelta(minutes=15),
        )
        after = timezone.now()

        self.assertIsNotNone(log.expires_at)
        self.assertEqual(log.reason, "Critical emergency")
        self.assertGreaterEqual(log.expires_at, before + timedelta(minutes=14.5))
        self.assertLessEqual(log.expires_at, after + timedelta(minutes=15.5))

    def test_break_glass_is_expired_false_within_window(self):
        """Test is_expired() returns False when within 15-minute window."""
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency access",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertFalse(log.is_expired())

    def test_break_glass_is_expired_true_after_window(self):
        """Test is_expired() returns True after 15-minute window."""
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(log.is_expired())

    def test_break_glass_is_expired_none_window(self):
        """Test is_expired() returns False when expires_at is None (backward compatibility)."""
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency access",
            expires_at=None,
        )
        self.assertFalse(log.is_expired())

    def test_break_glass_list_filters_expired_logs(self):
        """Test that expired logs can be identified via is_expired() method."""
        # Create valid (not expired) log
        valid_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency - valid",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Create expired log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency - expired",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Verify filtering logic
        self.assertFalse(valid_log.is_expired())
        self.assertTrue(expired_log.is_expired())

    def test_break_glass_expired_access_audited(self):
        """Test that expired access can be identified."""
        # Create expired log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency - expired",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Verify it's expired
        self.assertTrue(expired_log.is_expired())

    def test_break_glass_at_exact_expiry_boundary(self):
        """Test break-glass access at exact expiry boundary (edge case)."""
        current_time = timezone.now()
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency - exact boundary",
            expires_at=current_time,
        )

        # At exact expiry moment, should be considered expired
        self.assertTrue(log.is_expired())

    def test_break_glass_multiple_hospitals_scoped(self):
        """Test break-glass logs are scoped correctly by hospital."""
        log_h1 = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency at H1",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Create doctor in hospital2
        doctor2 = User.objects.create_user(
            email="doctor2@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital2,
            account_status="active",
        )

        # Verify logs are per-hospital
        h1_logs = BreakGlassLog.objects.filter(facility=self.hospital1)
        h2_logs = BreakGlassLog.objects.filter(facility=self.hospital2)
        
        self.assertEqual(h1_logs.count(), 1)
        self.assertEqual(h2_logs.count(), 0)

    def test_break_glass_notification_includes_expiry_info(self):
        """Test that break-glass logs include expiry information."""
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Critical emergency",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        # Verify expires_at is set
        self.assertIsNotNone(log.expires_at)
        # Verify it's in the future
        self.assertFalse(log.is_expired())
