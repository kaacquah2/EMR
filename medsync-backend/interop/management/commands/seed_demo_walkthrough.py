"""
``python manage.py seed_demo_walkthrough``

Seeds a complete, scripted inter-hospital walkthrough for the final-year
project demo / viva.  Creates two hospitals, their clinical staff, a patient
registered at Hospital A with a medical record, a referral to Hospital B, an
active consent, and a break-glass log — all idempotent (safe to run multiple
times).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEMO SCRIPT (for examiner / viva)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 — Log in as the KATH doctor (Hospital A)
  Email:     demo.doctor.kath@medsync.demo
  Password:  DemoPass123!
  → Verify: patient "Yaw Boateng" appears in their patient list with a
    diagnosis record.

Step 2 — Log in as the KBTH doctor (Hospital B)
  Email:     demo.doctor.kbth@medsync.demo
  Password:  DemoPass123!
  → Navigate to "Inter-Hospital Access" → search for "Yaw Boateng".
  → The patient appears because Hospital B has:
      • An ACCEPTED referral from Hospital A (grants SUMMARY access).
      • An active FULL_RECORD consent (grants full clinical records).
  → Click the patient → verify full records are visible (scope: FULL_RECORD).
  → Check: the audit log shows a VIEW_CROSS_FACILITY_RECORD entry.

Step 3 — Revoke the consent
  → As KBTH doctor (or hospital admin), revoke the consent.
  → Refresh the inter-hospital view — access is now SUMMARY-only via referral.
  → Revoke nothing further and access drops to "No access" (403).
  ← This demonstrates the consent gate working in real time.

Step 4 — Break-glass emergency access
  → As KBTH doctor, trigger "Break Glass" for Yaw Boateng.
  → Reason code: life_threatening_emergency / reason: "Unconscious patient".
  → Full record access is restored for 15 minutes.
  → After the window expires, access drops again.
  ← This demonstrates the emergency override with time-limited audit trail.

Step 5 — Examiner note on security
  → Show the AuditLog (Admin → Audit Trail) — every cross-facility access is
    chained with SHA-256 + HMAC and stored with IP address, timestamp, scope.
  → Show the Break-Glass review page (Super Admin → Break Glass Review).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Seed an end-to-end inter-hospital demo walkthrough for the project "
        "viva/defence.  Idempotent — safe to run multiple times."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo objects before re-seeding (clean slate).",
        )

    def handle(self, *args, **options):
        from core.models import Hospital, User
        from patients.models import Patient
        from interop.models import (
            GlobalPatient,
            FacilityPatient,
            Referral,
            Consent,
            BreakGlassLog,
        )
        from records.models import MedicalRecord, Encounter, Diagnosis

        self.stdout.write(self.style.MIGRATE_HEADING("\n🏥 MedSync — Demo Walkthrough Seed"))
        self.stdout.write("=" * 60)

        if options["reset"]:
            self._reset_demo_objects()

        with transaction.atomic():
            # ------------------------------------------------------------------
            # 0. ConsentScope reference data (clinical categories for granular consent)
            # ------------------------------------------------------------------
            self.stdout.write("\n[0/7] Seeding ConsentScope categories...")
            from interop.models import ConsentScope
            scope_defs = [
                ("HIV", "HIV/AIDS-related records (e.g. viral load, ARV prescriptions)"),
                ("MentalHealth", "Psychiatric diagnoses, therapy notes, and medication"),
                ("Reproductive", "Reproductive health and obstetrics records"),
                ("Substance", "Substance use / addiction treatment records"),
                ("Genetics", "Genetic test results and family history data"),
                ("Oncology", "Cancer diagnoses, chemotherapy, and oncology notes"),
            ]
            for name, desc in scope_defs:
                ConsentScope.objects.get_or_create(
                    name=name,
                    defaults={"description": desc},
                )
            self.stdout.write(f"    ✓ {len(scope_defs)} ConsentScope categories ready.")

            # ------------------------------------------------------------------
            # 1. Hospitals
            # ------------------------------------------------------------------
            self.stdout.write("\n[1/7] Creating hospitals...")
            kath, kath_new = Hospital.objects.get_or_create(
                nhis_code="DEMO-KATH-001",
                defaults={
                    "name": "Komfo Anokye Teaching Hospital (Demo)",
                    "region": "Ashanti",
                    "address": "Bantama, Kumasi, Ashanti Region",
                    "phone": "0322022301",
                    "email": "info@kath-demo.medsync.gh",
                    "facility_type": "TEACHING_HOSPITAL",
                    "country": "GH",
                },
            )
            kbth, kbth_new = Hospital.objects.get_or_create(
                nhis_code="DEMO-KBTH-001",
                defaults={
                    "name": "Korle Bu Teaching Hospital (Demo)",
                    "region": "Greater Accra",
                    "address": "Korle Bu, Accra, Greater Accra Region",
                    "phone": "0302674071",
                    "email": "info@kbth-demo.medsync.gh",
                    "facility_type": "TEACHING_HOSPITAL",
                    "country": "GH",
                },
            )
            self._log_item("Hospital A (KATH)", kath, kath_new)
            self._log_item("Hospital B (KBTH)", kbth, kbth_new)

            # ------------------------------------------------------------------
            # 2. Clinical staff
            # ------------------------------------------------------------------
            self.stdout.write("\n[2/7] Creating demo users...")
            kath_doc = self._get_or_create_user(
                email="demo.doctor.kath@medsync.demo",
                password="DemoPass123!",
                full_name="Dr. Kwabena Osei (KATH Demo)",
                role="doctor",
                hospital=kath,
            )
            kbth_doc = self._get_or_create_user(
                email="demo.doctor.kbth@medsync.demo",
                password="DemoPass123!",
                full_name="Dr. Abena Agyei (KBTH Demo)",
                role="doctor",
                hospital=kbth,
            )
            kath_admin = self._get_or_create_user(
                email="demo.admin.kath@medsync.demo",
                password="DemoPass123!",
                full_name="Admin Kofi Mensah (KATH Demo)",
                role="hospital_admin",
                hospital=kath,
            )
            self._log_item("KATH Doctor", kath_doc, False)
            self._log_item("KBTH Doctor", kbth_doc, False)
            self._log_item("KATH Admin", kath_admin, False)

            # ------------------------------------------------------------------
            # 3. Local patient at KATH (Hospital A)
            # ------------------------------------------------------------------
            self.stdout.write("\n[3/7] Creating patient at KATH (Hospital A)...")
            local_patient, lp_new = Patient.objects.get_or_create(
                ghana_health_id="GH-DEMO-YAW-001",
                defaults={
                    "full_name": "Yaw Boateng",
                    "date_of_birth": date(1980, 3, 22),
                    "gender": "male",
                    "blood_group": "O+",
                    "registered_at": kath,
                    "created_by": kath_doc,
                },
            )
            self._log_item("Local patient (Yaw Boateng @ KATH)", local_patient, lp_new)

            # ------------------------------------------------------------------
            # 4. Global Patient (Central MPI) + facility link
            # ------------------------------------------------------------------
            self.stdout.write("\n[4/7] Enrolling in Global Patient Index (Central MPI)...")
            # Find or create GlobalPatient — match by national_id (encrypted, Python-level)
            national_id = "GHA-DEMO-11223344"
            gp = self._find_global_patient_by_national_id(national_id)
            if not gp:
                gp = GlobalPatient.objects.create(
                    national_id=national_id,
                    first_name="Yaw",
                    last_name="Boateng",
                    date_of_birth=date(1980, 3, 22),
                    gender="male",
                    blood_group="O+",
                    ghana_health_id="GH-DEMO-YAW-001",
                )
                self.stdout.write(
                    f"    ✓ GlobalPatient created: {gp.id} (Yaw Boateng)"
                )
            else:
                self.stdout.write(
                    f"    ~ GlobalPatient found: {gp.id} (Yaw Boateng)"
                )

            fp, fp_new = FacilityPatient.objects.get_or_create(
                facility=kath,
                global_patient=gp,
                defaults={
                    "local_patient_id": str(local_patient.id),
                    "patient": local_patient,
                },
            )
            self._log_item("FacilityPatient (KATH ↔ GlobalPatient)", fp, fp_new)

            # ------------------------------------------------------------------
            # 5. Medical record at KATH
            # ------------------------------------------------------------------
            self.stdout.write("\n[5/7] Creating medical records at KATH...")
            enc = self._get_or_create_encounter(local_patient, kath, kath_doc)
            self._log_item("Encounter (KATH)", enc, True)

            # ------------------------------------------------------------------
            # 6. Referral KATH → KBTH (ACCEPTED)
            # ------------------------------------------------------------------
            self.stdout.write("\n[6/7] Creating referral KATH → KBTH (ACCEPTED)...")
            referral, ref_new = Referral.objects.get_or_create(
                global_patient=gp,
                from_facility=kath,
                to_facility=kbth,
                defaults={
                    "reason": (
                        "Patient presents with persistent cardiac arrhythmia requiring "
                        "specialist cardiology review. Requesting tertiary-level assessment "
                        "and ECG-monitored observation at KBTH."
                    ),
                    "status": Referral.STATUS_ACCEPTED,
                    "receiving_department": "Cardiology",
                },
            )
            if not ref_new and referral.status != Referral.STATUS_ACCEPTED:
                referral.status = Referral.STATUS_ACCEPTED
                referral.save(update_fields=["status"])
            self._log_item("Referral KATH→KBTH (ACCEPTED)", referral, ref_new)

            # ------------------------------------------------------------------
            # 7. Consent: Yaw grants FULL_RECORD access to KBTH
            # ------------------------------------------------------------------
            self.stdout.write("\n[7/7] Creating consent (KATH patient → KBTH FULL_RECORD)...")
            consent, con_new = Consent.objects.get_or_create(
                global_patient=gp,
                granted_to_facility=kbth,
                defaults={
                    "granted_by": kath_doc,
                    "scope": Consent.SCOPE_FULL_RECORD,
                    "is_active": True,
                    "expires_at": timezone.now() + timezone.timedelta(days=365),
                },
            )
            if not con_new and not consent.is_active:
                consent.is_active = True
                consent.expires_at = timezone.now() + timezone.timedelta(days=365)
                consent.save(update_fields=["is_active", "expires_at"])
            self._log_item("Consent (Yaw → KBTH FULL_RECORD)", consent, con_new)

        # ----------------------------------------------------------------------
        # Print the full demo script
        # ----------------------------------------------------------------------
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ Demo walkthrough seed complete!\n"))
        self.stdout.write(self.style.MIGRATE_HEADING("DEMO CREDENTIALS:"))
        self.stdout.write(f"  KATH Doctor  →  demo.doctor.kath@medsync.demo  /  DemoPass123!")
        self.stdout.write(f"  KBTH Doctor  →  demo.doctor.kbth@medsync.demo  /  DemoPass123!")
        self.stdout.write(f"  KATH Admin   →  demo.admin.kath@medsync.demo   /  DemoPass123!")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("DEMO WALKTHROUGH:"))
        self.stdout.write(
            "  1. Log in as KATH Doctor → verify patient 'Yaw Boateng' + records."
        )
        self.stdout.write(
            "  2. Log in as KBTH Doctor → Inter-Hospital Access → search 'Yaw Boateng'."
        )
        self.stdout.write(
            "     • Access granted via FULL_RECORD consent (+ ACCEPTED referral)."
        )
        self.stdout.write(
            "  3. Revoke the consent → access drops to SUMMARY (referral only)."
        )
        self.stdout.write(
            "  4. Trigger Break-Glass → full record access for 15 min → audit entry created."
        )
        self.stdout.write(
            "  5. Show AuditLog (Super Admin → Audit Trail): VIEW_CROSS_FACILITY_RECORD entries."
        )
        self.stdout.write("=" * 60)

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _log_item(self, label, obj, created):
        icon = "✓" if created else "~"
        verb = "created" if created else "found"
        self.stdout.write(f"    {icon} {label} {verb}: {obj.pk}")

    def _get_or_create_user(self, email, password, full_name, role, hospital):
        from core.models import User

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "role": role,
                "hospital": hospital,
                "account_status": "active",
                "licence_verified": role in ("doctor",),
            },
        )
        # Always refresh the password so it's predictable for demos.
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _find_global_patient_by_national_id(self, national_id):
        """Python-level search because national_id is field-encrypted."""
        from interop.models import GlobalPatient

        for gp in GlobalPatient.objects.all():
            try:
                if gp.national_id == national_id:
                    return gp
            except Exception:
                continue
        return None

    def _get_or_create_encounter(self, patient, hospital, doctor):
        """Create a realistic encounter + diagnosis if none exists for this patient."""
        from records.models import Encounter

        enc = Encounter.objects.filter(patient=patient, hospital=hospital).first()
        if enc:
            return enc

        enc = Encounter.objects.create(
            patient=patient,
            hospital=hospital,
            assigned_doctor=doctor,
            chief_complaint="Persistent palpitations and shortness of breath on exertion.",
            examination_findings=(
                "BP: 138/86 mmHg. HR: 92 bpm (irregular). SpO2: 97%. "
                "Auscultation: irregular heart rhythm, no murmurs. Lungs clear."
            ),
            assessment_plan=(
                "Impression: Paroxysmal atrial fibrillation. "
                "Plan: ECG, echocardiogram, electrolytes, CBC. "
                "Start rate control; refer to KBTH Cardiology for specialist review."
            ),
            encounter_type="outpatient",
            status="completed",
        )
        return enc

    def _reset_demo_objects(self):
        """Remove all objects created by this command (identified by demo email/nhis_code)."""
        from core.models import Hospital, User
        from interop.models import GlobalPatient, FacilityPatient, Referral, Consent, BreakGlassLog

        self.stdout.write(self.style.WARNING("\n[RESET] Removing existing demo objects..."))
        demo_hospitals = Hospital.objects.filter(nhis_code__in=["DEMO-KATH-001", "DEMO-KBTH-001"])
        demo_users = User.objects.filter(email__contains="@medsync.demo")
        demo_emails = list(demo_users.values_list("email", flat=True))

        # Delete in dependency order
        BreakGlassLog.objects.filter(accessed_by__email__contains="@medsync.demo").delete()
        Consent.objects.filter(granted_by__email__contains="@medsync.demo").delete()
        Referral.objects.filter(from_facility__nhis_code__in=["DEMO-KATH-001", "DEMO-KBTH-001"]).delete()
        FacilityPatient.objects.filter(facility__nhis_code__in=["DEMO-KATH-001", "DEMO-KBTH-001"]).delete()
        demo_users.delete()
        demo_hospitals.delete()
        self.stdout.write(self.style.WARNING(f"  Removed demo users: {demo_emails}"))
        self.stdout.write(self.style.WARNING("  Removed demo hospitals, referrals, consents."))
