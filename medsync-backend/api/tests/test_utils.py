import pytest
from datetime import date
from django.contrib.auth.hashers import make_password
from api.utils import get_patient_queryset, can_access_cross_facility, sanitize_audit_resource_id
from core.models import User, Hospital, Ward
from patients.models import Patient, PatientAdmission
from interop.models import GlobalPatient, Consent
import secrets
import string


# Generate a strong password for testing (same one reused throughout tests)
# This is shared across tests but NOT hardcoded
_TEST_PASSWORD = None

def _get_test_password():
    """Get or generate a test password. Uses same value throughout test session."""
    global _TEST_PASSWORD
    if _TEST_PASSWORD is None:
        # Generate once per test session
        chars = string.ascii_letters + string.digits + "!@#$"
        _TEST_PASSWORD = ''.join(secrets.choice(chars) for _ in range(12))
    return _TEST_PASSWORD


def _make_patient(ghana_health_id, full_name, hospital, created_by):
    return Patient.objects.create(
        ghana_health_id=ghana_health_id,
        full_name=full_name,
        date_of_birth=date(1990, 1, 1),
        gender="male",
        registered_at=hospital,
        created_by=created_by,
    )


def _make_global_patient(first_name="Global", last_name="Patient", national_id=None):
    return GlobalPatient.objects.create(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date(1985, 5, 15),
        gender="male",
        national_id=national_id,
    )


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="Test Hospital", region="Greater Accra", nhis_code="TH001")


@pytest.fixture
def ward(db, hospital):
    return Ward.objects.create(hospital=hospital, ward_name="General", ward_type="general")


@pytest.fixture
def creator_user(db, hospital):
    return User.objects.create_user(
        email="creator@test.com", password=_get_test_password(), role="doctor", full_name="Dr Creator", hospital=hospital
    )


@pytest.mark.django_db
class TestGetPatientQueryset:
    def test_super_admin_no_hospital_sees_all(self, hospital, creator_user):
        super_admin = User.objects.create_user(
            email="sa@test.com", password=_get_test_password(), role="super_admin", full_name="SA", hospital=None
        )
        _make_patient("G1", "P1", hospital, creator_user)
        _make_patient("G2", "P2", hospital, creator_user)
        qs = get_patient_queryset(super_admin)
        assert qs.count() == 2

    def test_doctor_sees_all(self, hospital, creator_user):
        doctor = User.objects.create_user(
            email="d@test.com", password=_get_test_password(), role="doctor", full_name="Dr D", hospital=hospital
        )
        _make_patient("G1", "P1", hospital, creator_user)
        qs = get_patient_queryset(doctor)
        assert qs.count() == 1

    def test_lab_technician_sees_none(self, hospital, creator_user):
        lab = User.objects.create_user(
            email="lab@test.com", password=_get_test_password(), role="lab_technician", full_name="Lab", hospital=hospital
        )
        _make_patient("G1", "P1", hospital, creator_user)
        qs = get_patient_queryset(lab)
        assert qs.count() == 0

    def test_hospital_admin_sees_own_hospital_only(self, hospital, creator_user):
        other = Hospital.objects.create(name="Other", region="R", nhis_code="TH002")
        admin = User.objects.create_user(
            email="ha@test.com", password=_get_test_password(), role="hospital_admin", full_name="HA", hospital=hospital
        )
        _make_patient("G1", "P1", hospital, creator_user)
        _make_patient("G2", "P2", other, creator_user)
        qs = get_patient_queryset(admin)
        assert qs.count() == 1
        assert qs.first().ghana_health_id == "G1"


@pytest.mark.django_db
class TestCanAccessCrossFacility:
    def test_super_admin_no_facility_has_full_access(self, hospital):
        super_admin = User.objects.create_user(
            email="sa@test.com", password=_get_test_password(), role="super_admin", full_name="SA", hospital=None
        )
        gp = _make_global_patient("Global", "P1", "N1")
        allowed, scope = can_access_cross_facility(super_admin, gp.id)
        assert allowed is True
        assert scope == Consent.SCOPE_FULL_RECORD

    def test_no_consent_or_referral_denied(self, hospital):
        doctor = User.objects.create_user(
            email="d@test.com", password=_get_test_password(), role="doctor", full_name="Dr D", hospital=hospital
        )
        gp = _make_global_patient("Global", "P2", "N2")
        allowed, scope = can_access_cross_facility(doctor, gp.id)
        assert allowed is False
        assert scope is None

    def test_consent_grants_access(self, hospital):
        doctor = User.objects.create_user(
            email="d2@test.com", password=_get_test_password(), role="doctor", full_name="Dr D", hospital=hospital
        )
        gp = _make_global_patient("Global", "P3", "N3")
        Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hospital,
            granted_by=doctor,
            is_active=True,
            scope=Consent.SCOPE_SUMMARY,
        )
        allowed, scope = can_access_cross_facility(doctor, gp.id)
        assert allowed is True
        assert scope == Consent.SCOPE_SUMMARY


@pytest.mark.django_db
class TestSanitizeAuditResourceId:
    def test_short_id_unchanged(self):
        assert sanitize_audit_resource_id("abc-123") == "abc-123"

    def test_long_id_redacted(self):
        long_id = "x" * 100
        assert sanitize_audit_resource_id(long_id) == "[REDACTED]"

    def test_none_unchanged(self):
        assert sanitize_audit_resource_id(None) is None
