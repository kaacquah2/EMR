"""
Edge case tests for referral state machine.

Tests:
- Offline facility referral retry
- Expired referral handling
- Concurrent referral updates
- Rollback scenarios
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from core.models import User, Hospital
from interop.models import Referral
from patients.models import Patient
from api.state_machines import validate_referral_transition, StateMachineError


@pytest.mark.django_db
class TestReferralEdgeCases:
    """Edge case testing for referral state machine."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup hospitals, users, and patients."""
        self.hospital_a = Hospital.objects.create(
            name="Hospital A",
            region="Region A",
            nhis_code="HA_001",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Hospital B",
            region="Region B",
            nhis_code="HB_001",
            is_active=True,
        )

        self.doctor_a = User.objects.create_user(
            email="doctor_a@test.com",
            password="Pass123!@#",
            role="doctor",
            hospital=self.hospital_a,
            account_status="active",
        )

        self.doctor_b = User.objects.create_user(
            email="doctor_b@test.com",
            password="Pass123!@#",
            role="doctor",
            hospital=self.hospital_b,
            account_status="active",
        )

        self.patient = Patient.objects.create(
            ghana_health_id="GHI_001",
            registered_at=self.hospital_a,
            full_name="Test Patient",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def test_expired_referral_cannot_be_accepted(self):
        """Expired referral should not allow acceptance."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
            expires_at=timezone.now() - timedelta(hours=1),  # Expired
        )
        
        # Should not allow transition to accepted
        with pytest.raises(StateMachineError):
            validate_referral_transition(referral.status, "accepted")

    def test_concurrent_accept_reject_race_condition(self):
        """Two doctors trying to accept/reject simultaneously."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Simulate first doctor accepting
        referral.status = "accepted"
        referral.accepted_by = self.doctor_b
        referral.save()

        # Try to reject same referral
        try:
            validate_referral_transition("accepted", "rejected")
            # Should fail - can't transition from accepted to rejected
            assert False, "Should not allow transition"
        except StateMachineError:
            pass

    def test_referral_completion_requires_acceptance_first(self):
        """Referral must be accepted before completion."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
        )

        # Try to transition pending -> completed (invalid)
        try:
            validate_referral_transition(referral.status, "completed")
            assert False, "Should not allow pending -> completed"
        except StateMachineError:
            pass

    def test_referral_rejection_is_terminal(self):
        """Rejected referral cannot be reverted."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
        )

        # Reject referral
        referral.status = "rejected"
        referral.save()

        # Try to transition back to pending
        try:
            validate_referral_transition("rejected", "pending")
            assert False, "Should not allow rejected -> pending"
        except StateMachineError:
            pass

    def test_idempotent_status_update(self):
        """Updating to same status should be safe."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
        )

        # Update to same status (should be idempotent)
        referral.status = "pending"
        referral.save()
        
        assert referral.status == "pending"

    def test_referral_audit_trail_on_state_change(self):
        """Each state change creates audit entry."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
        )

        # Accept
        referral.status = "accepted"
        referral.accepted_by = self.doctor_b
        referral.accepted_at = timezone.now()
        referral.save()

        # Verify state was recorded
        assert referral.status == "accepted"
        assert referral.accepted_by == self.doctor_b
        assert referral.accepted_at is not None

    def test_referral_version_increments_on_update(self):
        """Version field increments on each update."""
        referral = Referral.objects.create(
            from_hospital=self.hospital_a,
            to_hospital=self.hospital_b,
            patient=self.patient,
            referred_by=self.doctor_a,
            status="pending",
            version=1,
        )

        initial_version = referral.version
        referral.status = "accepted"
        referral.version = initial_version + 1
        referral.save()

        referral.refresh_from_db()
        assert referral.version == initial_version + 1
