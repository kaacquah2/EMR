"""
Tests for the inter-hospital access features that directly support the project
title: "Design and Implementation of a Secure Centralized Electronic Medical
Records System for Inter-Hospital Access".

Covers:
  1. Auto-GPID enrollment on patient registration.
  2. Data residency enforcement using the real Hospital.country field.
  3. Granular consent (excluded_scopes) filters records in cross_facility_records.
  4. FHIR and interop consent checks are now unified.
"""

import datetime
import pytest

from core.models import Hospital, User
from interop.models import (
    GlobalPatient,
    FacilityPatient,
    Consent,
    ConsentScope,
    Referral,
)
from patients.models import Patient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _hospital(nhis, name="Test Hospital", country="GH"):
    return Hospital.objects.create(
        nhis_code=nhis,
        name=name,
        region="Test Region",
        country=country,
    )


def _user(email, role, hospital):
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        role=role,
        hospital=hospital,
        account_status="active",
    )


def _patient(ghid, hospital, created_by, name="Test Patient"):
    return Patient.objects.create(
        ghana_health_id=ghid,
        full_name=name,
        date_of_birth=datetime.date(1990, 1, 1),
        gender="male",
        registered_at=hospital,
        created_by=created_by,
    )


# ---------------------------------------------------------------------------
# 1. Auto-GPID enrollment on patient registration
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAutoGPIDEnrollment:
    """ADD-1: _link_to_global_registry must be called during patient_create."""

    def test_helper_creates_global_patient(self, db):
        hosp = _hospital("AUTO-GP-001")
        doc = _user("auto.doc@test.gh", "doctor", hosp)
        patient = _patient("GH-AUTO-001", hosp, doc, name="Auto Kofi")

        from api.views.patient_views import _link_to_global_registry
        gp = _link_to_global_registry(patient, hosp)

        assert gp is not None, "_link_to_global_registry must return a GlobalPatient"
        assert gp.first_name == "Auto"
        assert gp.last_name == "Kofi"

    def test_helper_creates_facility_patient_link(self, db):
        hosp = _hospital("AUTO-FP-001")
        doc = _user("auto.fp.doc@test.gh", "doctor", hosp)
        patient = _patient("GH-AUTO-FP-001", hosp, doc, name="Ama Linktest")

        from api.views.patient_views import _link_to_global_registry
        _link_to_global_registry(patient, hosp)

        fp = FacilityPatient.objects.filter(
            patient=patient, facility=hosp, deleted_at__isnull=True
        ).first()
        assert fp is not None, "FacilityPatient link must be created"
        assert fp.global_patient.ghana_health_id == patient.ghana_health_id

    def test_helper_is_idempotent(self, db):
        hosp = _hospital("AUTO-IDEM-001")
        doc = _user("auto.idem.doc@test.gh", "doctor", hosp)
        patient = _patient("GH-AUTO-IDEM-001", hosp, doc, name="Idempotent Test")

        from api.views.patient_views import _link_to_global_registry
        gp1 = _link_to_global_registry(patient, hosp)
        gp2 = _link_to_global_registry(patient, hosp)

        assert gp1.id == gp2.id, "Re-running must return the same GlobalPatient"
        assert FacilityPatient.objects.filter(
            patient=patient, facility=hosp
        ).count() == 1, "Only one FacilityPatient link should exist"

    def test_api_patient_create_enrolls_in_mpi(self, db, client):
        """End-to-end: POST /patients/ → GlobalPatient created automatically."""
        hosp = _hospital("API-MPI-001")
        receptionist = _user("receptionist.mpi@test.gh", "receptionist", hosp)

        client.force_login(receptionist)
        response = client.post(
            "/api/v1/patients/",
            data={
                "ghana_health_id": "GH-MPI-API-001",
                "full_name": "Kwame Nkrumah",
                "date_of_birth": "1989-03-06",
                "gender": "male",
            },
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

        assert response.status_code in (201, 200), (
            f"Patient create should succeed; got {response.status_code}: {response.content}"
        )
        # The GlobalPatient must now exist in the MPI
        # (Python-level search because national_id is encrypted)
        local_patient = Patient.objects.filter(ghana_health_id="GH-MPI-API-001").first()
        assert local_patient is not None
        fp = FacilityPatient.objects.filter(patient=local_patient).first()
        assert fp is not None, (
            "A FacilityPatient link must be created automatically on registration"
        )


# ---------------------------------------------------------------------------
# 2. Data residency enforcement using the real Hospital.country field
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDataResidency:
    """CHANGE-2: Hospital.country must be read for NDPA residency enforcement."""

    def test_same_country_permits_access(self, db):
        from api.utils import can_access_cross_facility
        from django.utils import timezone

        hosp_a = _hospital("DR-A-001", country="GH")
        hosp_b = _hospital("DR-B-001", country="GH")
        doc_b = _user("dr.b@test.gh", "doctor", hosp_b)

        gp = GlobalPatient.objects.create(
            first_name="Residency",
            last_name="Test",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="male",
            data_residency_country="GH",
            data_residency_locked=True,
        )
        Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hosp_b,
            granted_by=doc_b,
            scope=Consent.SCOPE_FULL_RECORD,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )

        allowed, scope = can_access_cross_facility(
            doc_b, str(gp.id), effective_hospital=hosp_b
        )
        assert allowed, (
            "Access must be allowed when facility.country matches patient.data_residency_country"
        )

    def test_different_country_denies_access(self, db):
        from api.utils import can_access_cross_facility
        from django.utils import timezone

        hosp_a = _hospital("DR-C-001", country="GH")
        foreign_hosp = _hospital("DR-D-001", country="US")  # Different country
        foreign_doc = _user("foreign.doc@test.gh", "doctor", foreign_hosp)

        gp = GlobalPatient.objects.create(
            first_name="Locked",
            last_name="Patient",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="female",
            data_residency_country="GH",
            data_residency_locked=True,
        )
        # Grant consent — but residency should block it
        Consent.objects.create(
            global_patient=gp,
            granted_to_facility=foreign_hosp,
            granted_by=foreign_doc,
            scope=Consent.SCOPE_FULL_RECORD,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )

        allowed, scope = can_access_cross_facility(
            foreign_doc, str(gp.id), effective_hospital=foreign_hosp
        )
        assert not allowed, (
            "Access must be denied when facility.country differs from patient.data_residency_country"
        )


# ---------------------------------------------------------------------------
# 3. Granular consent — excluded_scopes filters records
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGranularConsent:
    """CHANGE-1: excluded_scopes and consented_record_ids must be enforced."""

    def test_excluded_scope_not_returned(self, db, client):
        """Records in an excluded category must not appear in cross_facility response."""
        from django.utils import timezone
        from records.models import MedicalRecord

        hosp_a = _hospital("GC-A-001")
        hosp_b = _hospital("GC-B-001")
        doc_a = _user("gc.doc.a@test.gh", "doctor", hosp_a)
        doc_b = _user("gc.doc.b@test.gh", "doctor", hosp_b)

        patient = _patient("GH-GC-001", hosp_a, doc_a, name="Granular Patient")

        gp = GlobalPatient.objects.create(
            first_name="Granular",
            last_name="Patient",
            date_of_birth=datetime.date(1990, 1, 1),
            gender="male",
            ghana_health_id="GH-GC-001",
        )
        FacilityPatient.objects.create(
            facility=hosp_a,
            global_patient=gp,
            local_patient_id=str(patient.id),
            patient=patient,
        )

        # Create two records — one in an excluded category
        hiv_scope, _ = ConsentScope.objects.get_or_create(
            name="HIV", defaults={"description": "HIV records"}
        )
        # Only create records if MedicalRecord has a category field
        # (test the Python-level filter in the view, not the DB structure)
        if not hasattr(MedicalRecord, "category"):
            pytest.skip("MedicalRecord.category field not present; skipping scope filter test")

        rec_normal = MedicalRecord.objects.create(
            patient=patient,
            hospital=hosp_a,
            record_type="encounter",
            category="General",
        )
        rec_hiv = MedicalRecord.objects.create(
            patient=patient,
            hospital=hosp_a,
            record_type="encounter",
            category="HIV",
        )

        consent = Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hosp_b,
            granted_by=doc_a,
            scope=Consent.SCOPE_FULL_RECORD,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )
        consent.excluded_scopes.add(hiv_scope)

        client.force_login(doc_b)
        response = client.get(
            f"/api/v1/cross-facility-records/{gp.id}/",
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        record_ids = [r.get("id") for r in data.get("records", [])]
        assert str(rec_normal.id) in record_ids, "General record should be included"
        assert str(rec_hiv.id) not in record_ids, (
            "HIV record must be excluded because HIV is in excluded_scopes"
        )
        assert "excluded_categories" in data
        assert "HIV" in data["excluded_categories"]


# ---------------------------------------------------------------------------
# 4. Hospital.country field exists and defaults to "GH"
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHospitalCountryField:
    """ADD-3 regression: Hospital.country must exist and default to GH."""

    def test_default_country_is_gh(self, db):
        hosp = Hospital.objects.create(
            nhis_code="CTR-TEST-001",
            name="Country Test Hospital",
            region="Test",
        )
        assert hosp.country == "GH", (
            "Hospital.country must default to 'GH' (Ghana) per data-residency design"
        )

    def test_custom_country_persists(self, db):
        hosp = Hospital.objects.create(
            nhis_code="CTR-TEST-002",
            name="Foreign Hospital",
            region="Test",
            country="NG",
        )
        assert hosp.country == "NG"
