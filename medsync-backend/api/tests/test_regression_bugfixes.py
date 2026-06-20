"""
Regression tests for bugs fixed in the 'fix all' pass.

Each test class documents the bug it covers and asserts the correct
post-fix behaviour so the issue cannot silently regress.
"""

import datetime
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.test import RequestFactory

from core.models import AuditLog, Hospital, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(hospital, role="doctor", suffix=""):
    return User.objects.create_user(
        email=f"{role}{suffix}@regression.test",
        password="TestPass123!",
        role=role,
        hospital=hospital,
        account_status="active",
    )


# ---------------------------------------------------------------------------
# Bug: Anomaly alert create_anomaly_alert always failed to write
#   - ip_address="system" is not a valid GenericIPAddressField value
#   - details= is not a field on AuditLog (correct field is extra_data)
# Fix: ip_address=None, extra_data={...}
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnomalyAlertWrite:
    """B1 regression: create_anomaly_alert must produce an AuditLog row."""

    def test_creates_audit_log_row(self, db):
        hospital = Hospital.objects.create(
            name="Test Hospital Anomaly",
            region="Test",
            nhis_code="ANOMALY001",
            is_active=True,
        )
        user = _make_user(hospital, suffix="_anomaly")

        from api.middleware.anomaly_detection import create_anomaly_alert

        before = AuditLog.objects.filter(user=user, action="ANOMALY_DETECTED").count()
        create_anomaly_alert(user, patient_count=5, window_hours=1)
        after = AuditLog.objects.filter(user=user, action="ANOMALY_DETECTED").count()

        assert after == before + 1, (
            "create_anomaly_alert should write one ANOMALY_DETECTED AuditLog row"
        )

    def test_row_has_correct_extra_data(self, db):
        hospital = Hospital.objects.create(
            name="Test Hospital Anomaly2",
            region="Test",
            nhis_code="ANOMALY002",
            is_active=True,
        )
        user = _make_user(hospital, suffix="_anomaly2")

        from api.middleware.anomaly_detection import create_anomaly_alert

        create_anomaly_alert(user, patient_count=7, window_hours=2)
        log = AuditLog.objects.filter(user=user, action="ANOMALY_DETECTED").latest("timestamp")

        assert log.ip_address is None, "ip_address should be None for system-generated alerts"
        assert log.extra_data is not None, "extra_data must be populated"
        assert log.extra_data.get("patient_count") == 7
        assert log.extra_data.get("alert_type") == "excessive_patient_access"


# ---------------------------------------------------------------------------
# Bug: patient_search filtered date_of_birth at the DB level on an encrypted
#      column — the ciphertext never matched any plaintext value, so results
#      were always empty.
# Fix: Python-level filtering after fetching the hospital-scoped queryset.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEncryptedDOBSearch:
    """A2 regression: patient DOB search must find matching encrypted records."""

    def test_dob_search_finds_patient(self, db, client):
        from patients.models import Patient

        hospital = Hospital.objects.create(
            name="DOB Search Hospital",
            region="Test",
            nhis_code="DOBSRCH001",
            is_active=True,
        )
        doctor = _make_user(hospital, role="doctor", suffix="_dob")

        target_dob = datetime.date(1985, 6, 15)
        patient = Patient.objects.create(
            ghana_health_id="GHA-DOB-001",
            full_name="Kofi Mensah",
            date_of_birth=target_dob,
            gender="male",
            registered_at=hospital,
            created_by=doctor,
        )
        # Create a decoy patient with a different DOB
        Patient.objects.create(
            ghana_health_id="GHA-DOB-002",
            full_name="Ama Serwaa",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="female",
            registered_at=hospital,
            created_by=doctor,
        )

        client.force_login(doctor)
        response = client.get(
            "/api/v1/patients/search/",
            {"dob": "1985-06-15"},
            HTTP_ACCEPT="application/json",
        )

        assert response.status_code == 200
        data = response.json().get("data", [])
        ids = [p.get("id") or p.get("ghana_health_id") for p in data]
        assert any("GHA-DOB-001" in str(i) for i in ids), (
            "DOB search must return the patient with matching date_of_birth"
        )
        assert not any("GHA-DOB-002" in str(i) for i in ids), (
            "DOB search must not return patients with a different date_of_birth"
        )

    def test_invalid_dob_format_returns_400(self, db, client):
        hospital = Hospital.objects.create(
            name="DOB Format Hospital",
            region="Test",
            nhis_code="DOBFMT001",
            is_active=True,
        )
        doctor = _make_user(hospital, role="doctor", suffix="_dobfmt")

        client.force_login(doctor)
        response = client.get(
            "/api/v1/patients/search/",
            {"dob": "15-06-1985"},  # wrong format
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Bug: AuditLog chain ordering used only `timestamp` (auto_now_add) as the
#      sort key.  Two audit entries created in the same second could be ordered
#      differently at write vs verify time → false "invalid chain" results.
# Fix: Order by (timestamp, id) in both save() and the verifier.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditChainOrdering:
    """B4 regression: chain verification must tolerate same-second writes."""

    def test_chain_verifies_after_same_second_writes(self, db):
        hospital = Hospital.objects.create(
            name="Audit Chain Hospital",
            region="Test",
            nhis_code="CHAIN001",
            is_active=True,
        )
        user = _make_user(hospital, role="doctor", suffix="_chain")

        # Write two audit entries.  The second entry's chain must be verifiable
        # even if both share the same timestamp (a common scenario in tests
        # where the DB clock has second-level precision).
        AuditLog.objects.create(
            user=user,
            action="VIEW",
            resource_type="Patient",
            resource_id="entry-1",
            hospital=hospital,
        )
        AuditLog.objects.create(
            user=user,
            action="VIEW",
            resource_type="Patient",
            resource_id="entry-2",
            hospital=hospital,
        )

        from api.services.audit_service import compute_audit_chain_status

        result = compute_audit_chain_status(max_users=10, max_logs_per_user=100)
        assert result["status"] == "valid", (
            f"Audit chain must be valid after consecutive writes: {result}"
        )


# ---------------------------------------------------------------------------
# Bug: Break-glass _audit_emergency manually computed chain_hash and passed
#      it to AuditLog.objects.create().  AuditLog.save() unconditionally
#      recomputes chain_hash for new rows, so the passed value was discarded —
#      and resource_id was a raw UUID object bypassing sanitize_audit_resource_id.
# Fix: Drop the manual computation; let save() handle it.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBreakGlassAudit:
    """B3 regression: break-glass audit must write via the standard chain path."""

    def test_emergency_audit_row_written_with_valid_chain(self, db):
        hospital = Hospital.objects.create(
            name="Break Glass Hospital",
            region="Test",
            nhis_code="BG001",
            is_active=True,
        )
        user = _make_user(hospital, role="doctor", suffix="_bg")

        global_patient_id = "11111111-1111-1111-1111-111111111111"

        factory = RequestFactory()
        request = factory.post("/")
        request.user = user
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"

        from api.views.break_glass_views import _audit_emergency

        before = AuditLog.objects.filter(
            user=user, action="EMERGENCY_ACCESS"
        ).count()
        _audit_emergency(user, global_patient_id, request, hospital=hospital)
        after = AuditLog.objects.filter(
            user=user, action="EMERGENCY_ACCESS"
        ).count()

        assert after == before + 1, "Break-glass must write an EMERGENCY_ACCESS audit row"

        log = AuditLog.objects.filter(
            user=user, action="EMERGENCY_ACCESS"
        ).latest("timestamp")
        assert log.chain_hash, "chain_hash must be set by AuditLog.save()"
        assert log.signature, "HMAC signature must be set by AuditLog.save()"
        # resource_id must be a sanitized string, not a raw UUID object
        assert isinstance(log.resource_id, str), (
            "resource_id must be a string after sanitize_audit_resource_id()"
        )


# ---------------------------------------------------------------------------
# Bug: Audit action LOGIN_SUCCESS was not in AuditLog.ACTIONS (valid: LOGIN).
# Also: CONSENT_WITHDRAWN → CONSENT_REVOKED, and new actions BACKUP_CODE_CONSUMED
#       / MFA_ATTEMPTS_EXCEEDED must now be in the ACTIONS list.
# ---------------------------------------------------------------------------

class TestAuditActionConstants:
    """B2 regression: all action strings used in the codebase must be in ACTIONS."""

    REQUIRED_ACTIONS = {
        "LOGIN",
        "CONSENT_REVOKED",
        "BACKUP_CODE_CONSUMED",
        "MFA_ATTEMPTS_EXCEEDED",
        "ANOMALY_DETECTED",
        "EMERGENCY_ACCESS",
    }

    def test_all_required_actions_in_choices(self):
        defined = {code for code, _ in AuditLog.ACTIONS}
        missing = self.REQUIRED_ACTIONS - defined
        assert not missing, (
            f"These action codes are used in the codebase but missing from "
            f"AuditLog.ACTIONS: {missing}"
        )

    def test_login_success_not_in_actions(self):
        """LOGIN_SUCCESS was the wrong key; LOGIN is the correct one."""
        defined = {code for code, _ in AuditLog.ACTIONS}
        assert "LOGIN_SUCCESS" not in defined, (
            "LOGIN_SUCCESS should not be in AuditLog.ACTIONS; use LOGIN instead"
        )

    def test_consent_withdrawn_not_in_actions(self):
        """CONSENT_WITHDRAWN was the wrong key; CONSENT_REVOKED is the correct one."""
        defined = {code for code, _ in AuditLog.ACTIONS}
        assert "CONSENT_WITHDRAWN" not in defined, (
            "CONSENT_WITHDRAWN should not be in AuditLog.ACTIONS; use CONSENT_REVOKED"
        )
