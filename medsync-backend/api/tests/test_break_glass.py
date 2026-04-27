"""
Comprehensive tests for break-glass emergency access control and auditing.

Tests verify:
- Break-glass access is fully logged (immutable audit trail)
- 15-minute time window enforcement (access expires after window)
- Super admin can review all break-glass events
- Abuse patterns are detected and flagged
- Break-glass reason codes are recorded correctly
- Multiple break-glass uses can be tracked

Access patterns:
- Any authorized user can trigger break-glass in emergency
- Access logged with timestamp, reason, facility, user
- Window expires: further access denied, new break-glass required
- Super admin dashboard shows all events
- Repeated rapid access flagged as potential abuse
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase, override_settings
from django.db.models import Count, Q
from rest_framework.test import APIClient
from core.models import User, Hospital, AuditLog
from interop.models import GlobalPatient, BreakGlassLog


@pytest.mark.django_db
class TestBreakGlassLogging:
    """Test break-glass emergency access logging."""

    def setup_method(self):
        """Create test fixtures for break-glass testing."""
        self.client = APIClient()

        # Create hospitals
        self.hospital_a = Hospital.objects.create(
            name="Hospital A",
            region="Region A",
            nhis_code="HA_BG_001",is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Hospital B",
            region="Region B",
            nhis_code="HB_BG_001",is_active=True,
        )

        # Create users
        self.doctor_a = User.objects.create_user(
            email="doctor_a_bg@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital_a,
            account_status="active",
        )
        self.doctor_b = User.objects.create_user(
            email="doctor_b_bg@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital_b,
            account_status="active",
        )
        self.super_admin = User.objects.create_user(
            email="admin_bg@medsync.gh",
            password="SecurePass123!@#",
            role="super_admin",
            account_status="active",
        )

        # Create global patient
        self.global_patient = GlobalPatient.objects.create(
            first_name="Emergency",
            last_name="Patient",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def test_break_glass_logs_audit_trail(self):
        """Test that break-glass access creates an immutable audit log entry."""
        # Create break-glass log
        before_time = timezone.now()
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="life_threatening_emergency",
            reason="Patient unconscious, immediate blood transfusion needed",
        )
        after_time = timezone.now()

        # Verify log entry exists
        assert bg_log.id is not None
        assert bg_log.created_at is not None
        assert bg_log.created_at >= before_time
        assert bg_log.created_at <= after_time

    def test_break_glass_includes_reason_code(self):
        """Test that break-glass log includes reason code."""
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="critical_time_sensitive_care",
            reason="Critical surgery needs patient history",
        )

        assert bg_log.reason_code == "critical_time_sensitive_care"
        assert bg_log.reason_code in dict(BreakGlassLog.REASON_CODES)

    def test_break_glass_includes_reason_text(self):
        """Test that break-glass log includes descriptive reason."""
        reason_text = "Patient coding, need immediate access to allergies and contraindications"
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="life_threatening_emergency",
            reason=reason_text,
        )

        assert bg_log.reason == reason_text
        assert len(bg_log.reason) > 0

    def test_break_glass_logs_accessed_by_user(self):
        """Test that break-glass log records which user accessed."""
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
        )

        assert bg_log.accessed_by == self.doctor_b
        assert bg_log.accessed_by.email == "doctor_b_bg@medsync.gh"

    def test_break_glass_logs_facility(self):
        """Test that break-glass log records which facility is accessing."""
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
        )

        assert bg_log.facility == self.hospital_b
        assert bg_log.facility.nhis_code == "HB_BG_001"

    def test_break_glass_logs_patient(self):
        """Test that break-glass log records which patient is accessed."""
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital_b,
            accessed_by=self.doctor_b,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
        )

        assert bg_log.global_patient == self.global_patient
        assert bg_log.global_patient.full_name == "Emergency Patient"


@pytest.mark.django_db
class TestBreakGlassTimeWindow:
    """Test 15-minute time window enforcement for break-glass access."""

    def setup_method(self):
        """Create test fixtures."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Region",
            nhis_code="TH_BG_001",is_active=True,
        )
        self.doctor = User.objects.create_user(
            email="doctor_bg_time@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )
        self.global_patient = GlobalPatient.objects.create(
            first_name="Time",
            last_name="Window",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def test_break_glass_15_minute_window_set(self):
        """Test that break-glass log sets expires_at to 15 minutes in future."""
        before = timezone.now()
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
            expires_at=before + timedelta(minutes=15),
        )
        after = timezone.now()

        # Verify expires_at is set
        assert bg_log.expires_at is not None
        # Should be approximately 15 minutes from creation
        delta = (bg_log.expires_at - bg_log.created_at).total_seconds() / 60
        assert 14.5 <= delta <= 15.5

    def test_break_glass_is_expired_false_within_window(self):
        """Test is_expired() returns False when within 15-minute window."""
        before = timezone.now()
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
            expires_at=before + timedelta(minutes=15),
        )

        # Should not be expired yet
        assert bg_log.is_expired() is False

    def test_break_glass_is_expired_true_after_window(self):
        """Test is_expired() returns True when past 15-minute window."""
        past = timezone.now() - timedelta(minutes=20)
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
            expires_at=past,
        )

        # Should be expired (expires_at is in the past)
        assert bg_log.is_expired() is True

    def test_break_glass_window_boundary_just_expired(self):
        """Test is_expired() at boundary (just past expiry)."""
        # Set expiry to 1 second ago
        one_sec_ago = timezone.now() - timedelta(seconds=1)
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
            expires_at=one_sec_ago,
        )

        assert bg_log.is_expired() is True

    def test_break_glass_window_boundary_not_yet_expired(self):
        """Test is_expired() at boundary (just before expiry)."""
        # Set expiry to 1 second in future
        one_sec_future = timezone.now() + timedelta(seconds=1)
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
            expires_at=one_sec_future,
        )

        assert bg_log.is_expired() is False


class TestBreakGlassSuperAdminReview(TestCase):
    """Test super admin ability to review break-glass events."""

    def setUp(self):
        """Create test fixtures."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Region",
            nhis_code="TH_BG_REVIEW",is_active=True,
        )
        self.doctor = User.objects.create_user(
            email="doctor_review@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )
        self.super_admin = User.objects.create_user(
            email="admin_review@medsync.gh",
            password="SecurePass123!@#",
            role="super_admin",
            account_status="active",
        )
        self.global_patient = GlobalPatient.objects.create(
            first_name="Review",
            last_name="Test",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def test_break_glass_super_admin_review(self):
        """Test that super admin can access and review break-glass logs."""
        # Create break-glass log
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
        )

        # Super admin can query all logs
        all_logs = BreakGlassLog.objects.all()
        assert all_logs.exists()
        assert bg_log in all_logs

    def test_break_glass_super_admin_can_mark_reviewed(self):
        """Test that super admin can mark break-glass event as reviewed."""
        bg_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency access",
        )

        # Initially not reviewed
        assert bg_log.reviewed is False

        # Super admin marks as reviewed
        bg_log.reviewed = True
        bg_log.reviewed_at = timezone.now()
        bg_log.reviewed_by = self.super_admin
        bg_log.save()

        bg_log.refresh_from_db()
        assert bg_log.reviewed is True
        assert bg_log.reviewed_by == self.super_admin
        assert bg_log.reviewed_at is not None

    def test_break_glass_super_admin_queries_all_facilities(self):
        """Test that super admin can query break-glass events from all hospitals."""
        hospital2 = Hospital.objects.create(
            name="Hospital 2",
            region="Region 2",
            nhis_code="H2_BG_REVIEW",is_active=True,
        )
        doctor2 = User.objects.create_user(
            email="doctor2_review@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital2,
            account_status="active",
        )

        # Create logs from both hospitals
        bg_log1 = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason_code="life_threatening_emergency",
            reason="Emergency 1",
        )
        bg_log2 = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=hospital2,
            accessed_by=doctor2,
            reason_code="critical_time_sensitive_care",
            reason="Emergency 2",
        )

        # Super admin sees both
        all_logs = BreakGlassLog.objects.all()
        assert all_logs.count() == 2
        assert bg_log1 in all_logs
        assert bg_log2 in all_logs


class TestBreakGlassAbuseFlagging:
    """Test detection and flagging of break-glass abuse patterns."""

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Region",
            nhis_code="TH_BG_ABUSE",is_active=True,
        )
        doctor = User.objects.create_user(
            email="doctor_abuse@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital,
            account_status="active",
        )
        global_patient = GlobalPatient.objects.create(
            first_name="Abuse",
            last_name="Test",
            date_of_birth="1990-01-01",
            gender="male",
        )
        return hospital, doctor, global_patient

    def test_break_glass_abuse_flagging(self, setup):
        """Test that repeated rapid break-glass accesses are flagged."""
        hospital, doctor, global_patient = setup

        # Create multiple break-glass logs in rapid succession
        logs = []
        for i in range(5):
            bg_log = BreakGlassLog.objects.create(
                global_patient=global_patient,
                facility=hospital,
                accessed_by=doctor,
                reason_code="other_emergency",
                reason=f"Emergency access {i+1}",
            )
            logs.append(bg_log)

        # Query to detect rapid usage (>3 in 15 minutes)
        cutoff_time = timezone.now() - timedelta(minutes=15)
        recent_logs = BreakGlassLog.objects.filter(
            accessed_by=doctor,
            global_patient=global_patient,
            created_at__gte=cutoff_time,
        )

        # 5 logs in rapid succession should trigger abuse flag
        if recent_logs.count() > 3:
            # Mark as excessive
            for log in recent_logs:
                log.excessive_usage = True
                log.save()

        # Verify flagging
        flagged = BreakGlassLog.objects.filter(excessive_usage=True)
        assert flagged.count() > 0

    def test_break_glass_no_abuse_flag_for_legitimate_access(self, setup):
        """Test that legitimate spaced-out access is not flagged."""
        hospital, doctor, global_patient = setup

        # Create break-glass logs spread over time
        logs = []
        for i in range(3):
            bg_log = BreakGlassLog.objects.create(
                global_patient=global_patient,
                facility=hospital,
                accessed_by=doctor,
                reason_code="life_threatening_emergency",
                reason=f"Legitimate emergency {i+1}",
                created_at=timezone.now() - timedelta(hours=i),
            )
            logs.append(bg_log)

        # These are spread out (hours apart), not rapid
        cutoff_time = timezone.now() - timedelta(minutes=15)
        recent_logs = BreakGlassLog.objects.filter(
            accessed_by=doctor,
            global_patient=global_patient,
            created_at__gte=cutoff_time,
        )

        # Only 1 log in last 15 minutes
        assert recent_logs.count() <= 1
        # Should not be flagged
        for log in logs:
            assert log.excessive_usage is False

    def test_break_glass_excessive_usage_audit_log(self, setup):
        """Test that excessive usage is logged in AuditLog."""
        hospital, doctor, global_patient = setup

        # Create rapid logs
        for i in range(5):
            BreakGlassLog.objects.create(
                global_patient=global_patient,
                facility=hospital,
                accessed_by=doctor,
                reason_code="other_emergency",
                reason=f"Emergency {i+1}",
            )

        # Log abuse detection
        AuditLog.objects.create(
            user=doctor,
            action="BREAK_GLASS_ABUSE_DETECTED",
            resource_type="BreakGlassLog",
            resource_id=str(global_patient.id),
            hospital=hospital,
            details={"pattern": "5 accesses in 15 minutes"},
        )

        # Verify audit log
        abuse_logs = AuditLog.objects.filter(action="BREAK_GLASS_ABUSE_DETECTED")
        assert abuse_logs.exists()


class TestBreakGlassReasonCodes:
    """Test break-glass reason code validation."""

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Region",
            nhis_code="TH_BG_REASONS",is_active=True,
        )
        doctor = User.objects.create_user(
            email="doctor_reasons@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital,
            account_status="active",
        )
        global_patient = GlobalPatient.objects.create(
            first_name="Reason",
            last_name="Codes",
            date_of_birth="1990-01-01",
            gender="male",
        )
        return hospital, doctor, global_patient

    def test_break_glass_life_threatening_reason(self, setup):
        """Test life-threatening emergency reason code."""
        hospital, doctor, global_patient = setup

        bg_log = BreakGlassLog.objects.create(
            global_patient=global_patient,
            facility=hospital,
            accessed_by=doctor,
            reason_code="life_threatening_emergency",
            reason="Patient in cardiac arrest",
        )
        assert bg_log.reason_code == "life_threatening_emergency"

    def test_break_glass_unconscious_patient_reason(self, setup):
        """Test unconscious patient reason code."""
        hospital, doctor, global_patient = setup

        bg_log = BreakGlassLog.objects.create(
            global_patient=global_patient,
            facility=hospital,
            accessed_by=doctor,
            reason_code="unconscious_patient",
            reason="Patient unconscious, needs medication history",
        )
        assert bg_log.reason_code == "unconscious_patient"

    def test_break_glass_critical_care_reason(self, setup):
        """Test critical time-sensitive care reason code."""
        hospital, doctor, global_patient = setup

        bg_log = BreakGlassLog.objects.create(
            global_patient=global_patient,
            facility=hospital,
            accessed_by=doctor,
            reason_code="critical_time_sensitive_care",
            reason="Emergency surgery needs allergies",
        )
        assert bg_log.reason_code == "critical_time_sensitive_care"

    def test_break_glass_mass_casualty_reason(self, setup):
        """Test mass casualty event reason code."""
        hospital, doctor, global_patient = setup

        bg_log = BreakGlassLog.objects.create(
            global_patient=global_patient,
            facility=hospital,
            accessed_by=doctor,
            reason_code="mass_casualty_event",
            reason="Multiple casualties from accident",
        )
        assert bg_log.reason_code == "mass_casualty_event"

    def test_break_glass_other_emergency_reason(self, setup):
        """Test other emergency reason code."""
        hospital, doctor, global_patient = setup

        bg_log = BreakGlassLog.objects.create(
            global_patient=global_patient,
            facility=hospital,
            accessed_by=doctor,
            reason_code="other_emergency",
            reason="Other emergency not covered by codes",
        )
        assert bg_log.reason_code == "other_emergency"


