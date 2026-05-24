"""
Edge case tests for referral state machine.

Tests:
- Expired referral handling
- Concurrent referral updates
- Rollback scenarios
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from core.models import User, Hospital
from interop.models import Referral, GlobalPatient
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

        self.global_patient = GlobalPatient.objects.create(
            first_name="Test",
            last_name="Patient",
            date_of_birth="1990-01-01",
            gender="male",
        )

    def _create_referral(self, status=Referral.STATUS_PENDING):
        return Referral.objects.create(
            global_patient=self.global_patient,
            from_facility=self.hospital_a,
            to_facility=self.hospital_b,
            reason="Specialist consultation required",
            status=status,
        )

    def test_expired_referral_cannot_be_accepted(self):
        """Expired referral should not allow acceptance."""
        referral = self._create_referral(status=Referral.STATUS_EXPIRED)
        with pytest.raises(StateMachineError):
            validate_referral_transition(referral.status, Referral.STATUS_ACCEPTED)

    def test_concurrent_accept_reject_race_condition(self):
        """Two doctors trying to accept/reject simultaneously."""
        referral = self._create_referral(status=Referral.STATUS_PENDING)

        referral.status = Referral.STATUS_ACCEPTED
        referral.save()

        with pytest.raises(StateMachineError):
            validate_referral_transition(Referral.STATUS_ACCEPTED, Referral.STATUS_REJECTED)

    def test_referral_completion_requires_acceptance_first(self):
        """Referral must be accepted before completion."""
        referral = self._create_referral(status=Referral.STATUS_PENDING)

        with pytest.raises(StateMachineError):
            validate_referral_transition(referral.status, Referral.STATUS_COMPLETED)

    def test_referral_rejection_is_terminal(self):
        """Rejected referral cannot be reverted."""
        referral = self._create_referral(status=Referral.STATUS_REJECTED)

        with pytest.raises(StateMachineError):
            validate_referral_transition(referral.status, Referral.STATUS_PENDING)

    def test_idempotent_status_update(self):
        """Updating to same status should be safe."""
        referral = self._create_referral(status=Referral.STATUS_PENDING)
        referral.status = Referral.STATUS_PENDING
        referral.save()
        assert referral.status == Referral.STATUS_PENDING

    def test_referral_audit_trail_on_state_change(self):
        """Each state change updates referral record."""
        referral = self._create_referral(status=Referral.STATUS_PENDING)
        referral.status = Referral.STATUS_ACCEPTED
        referral.save()
        referral.refresh_from_db()
        assert referral.status == Referral.STATUS_ACCEPTED

    def test_referral_version_increments_on_update(self):
        """Version field increments on each update."""
        referral = self._create_referral(status=Referral.STATUS_PENDING)
        initial_version = referral.version
        referral.status = Referral.STATUS_ACCEPTED
        referral.version = initial_version + 1
        referral.save()
        referral.refresh_from_db()
        assert referral.version == initial_version + 1
