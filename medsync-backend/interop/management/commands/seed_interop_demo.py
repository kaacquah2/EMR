from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Hospital, User
from interop.models import GlobalPatient, FacilityPatient, Referral, Consent, BreakGlassLog
from patients.models import Patient
import uuid

class Command(BaseCommand):
    help = "Seed interop demo data for multi-hospital environment"

    def handle(self, *args, **options):
        self.stdout.write("[START] Seeding interop demo data...")

        with transaction.atomic():
            # 1. Create Hospitals
            kath, _ = Hospital.objects.get_or_create(
                nhis_code="HOSP-KATH-001",
                defaults={
                    "name": "Komfo Anokye Teaching Hospital",
                    "region": "Ashanti",
                    "address": "Kumasi",
                    "phone": "0322022301",
                    "email": "info@kath.gov.gh"
                }
            )
            kbth, _ = Hospital.objects.get_or_create(
                nhis_code="HOSP-KBTH-001",
                defaults={
                    "name": "Korle Bu Teaching Hospital",
                    "region": "Greater Accra",
                    "address": "Accra",
                    "phone": "0302674071",
                    "email": "info@kbth.gov.gh"
                }
            )
            ridge, _ = Hospital.objects.get_or_create(
                nhis_code="HOSP-RIDGE-001",
                defaults={
                    "name": "Ridge Regional Hospital",
                    "region": "Greater Accra",
                    "address": "Accra",
                    "phone": "0302228315",
                    "email": "info@ridgehospital.gov.gh"
                }
            )

            # 2. Create Doctors
            kath_doc, _ = User.objects.get_or_create(
                email="doctor.kath@medsync.gov.gh",
                defaults={
                    "full_name": "Dr. Ebenezer Asante",
                    "role": "doctor",
                    "hospital": kath,
                    "account_status": "active",
                    "licence_verified": True
                }
            )
            kath_doc.set_password("password123")
            kath_doc.save()

            kbth_doc, _ = User.objects.get_or_create(
                email="doctor.kbth@medsync.gov.gh",
                defaults={
                    "full_name": "Dr. Naa Lamley",
                    "role": "doctor",
                    "hospital": kbth,
                    "account_status": "active",
                    "licence_verified": True
                }
            )
            kbth_doc.set_password("password123")
            kbth_doc.save()

            ridge_doc, _ = User.objects.get_or_create(
                email="doctor.ridge@medsync.gov.gh",
                defaults={
                    "full_name": "Dr. Seth Tetteh",
                    "role": "doctor",
                    "hospital": ridge,
                    "account_status": "active",
                    "licence_verified": True
                }
            )
            ridge_doc.set_password("password123")
            ridge_doc.save()

            # 3. Create Global Patients
            def get_gp(nid):
                for gp in GlobalPatient.objects.all():
                    if gp.national_id == nid: return gp
                return None

            kwame = get_gp("GHA-12345678-1")
            if not kwame:
                kwame = GlobalPatient.objects.create(
                    national_id="GHA-12345678-1",
                    first_name="Kwame",
                    last_name="Mensah",
                    date_of_birth="1985-06-15",
                    gender="male",
                    blood_group="O+",
                    ghana_health_id="GH-88776655"
                )

            ama = get_gp("GHA-98765432-1")
            if not ama:
                ama = GlobalPatient.objects.create(
                    national_id="GHA-98765432-1",
                    first_name="Ama",
                    last_name="Serwaa",
                    date_of_birth="1992-11-20",
                    gender="female",
                    blood_group="A-",
                    ghana_health_id="GH-11223344"
                )

            kofi = get_gp("GHA-55443322-1")
            if not kofi:
                kofi = GlobalPatient.objects.create(
                    national_id="GHA-55443322-1",
                    first_name="Kofi",
                    last_name="Antwi",
                    date_of_birth="1978-02-10",
                    gender="male",
                    blood_group="B+",
                    ghana_health_id="GH-99008877"
                )

            # 4. Link Patients to Facilities (FacilityPatient)
            def get_lp(ghid, hosp):
                for p in Patient.objects.filter(registered_at=hosp):
                    if p.ghana_health_id == ghid: return p
                return None

            lp_kwame_kath = get_lp("GH-88776655", kath)
            if not lp_kwame_kath:
                lp_kwame_kath = Patient.objects.create(
                    ghana_health_id="GH-88776655",
                    registered_at=kath,
                    full_name="Kwame Mensah",
                    date_of_birth="1985-06-15",
                    gender="male",
                    created_by=kath_doc
                )
            FacilityPatient.objects.get_or_create(
                facility=kath,
                global_patient=kwame,
                defaults={"local_patient_id": str(lp_kwame_kath.id), "patient": lp_kwame_kath}
            )

            # Ama at Ridge (Source)
            lp_ama_ridge = get_lp("GH-11223344", ridge)
            if not lp_ama_ridge:
                lp_ama_ridge = Patient.objects.create(
                    ghana_health_id="GH-11223344",
                    registered_at=ridge,
                    full_name="Ama Serwaa",
                    date_of_birth="1992-11-20",
                    gender="female",
                    created_by=ridge_doc
                )
            FacilityPatient.objects.get_or_create(
                facility=ridge,
                global_patient=ama,
                defaults={"local_patient_id": str(lp_ama_ridge.id), "patient": lp_ama_ridge}
            )

            # Kofi at KATH (Source)
            lp_kofi_kath = get_lp("GH-99008877", kath)
            if not lp_kofi_kath:
                lp_kofi_kath = Patient.objects.create(
                    ghana_health_id="GH-99008877",
                    registered_at=kath,
                    full_name="Kofi Antwi",
                    date_of_birth="1978-02-10",
                    gender="male",
                    created_by=kath_doc
                )
            FacilityPatient.objects.get_or_create(
                facility=kath,
                global_patient=kofi,
                defaults={"local_patient_id": str(lp_kofi_kath.id), "patient": lp_kofi_kath}
            )

            # 5. Create Referrals
            # KATH -> KBTH (Kwame Mensah) - ACCEPTED
            Referral.objects.get_or_create(
                global_patient=kwame,
                from_facility=kath,
                to_facility=kbth,
                status="ACCEPTED",
                defaults={"reason": "Cardiac evaluation for persistent arrhythmias."}
            )

            # Ridge -> KATH (Ama Serwaa) - PENDING
            Referral.objects.get_or_create(
                global_patient=ama,
                from_facility=ridge,
                to_facility=kath,
                status="PENDING",
                defaults={"reason": "Specialized orthopedic consultation for complex fracture."}
            )

            # KATH -> Ridge (Kofi Antwi) - COMPLETED
            Referral.objects.get_or_create(
                global_patient=kofi,
                from_facility=kath,
                to_facility=ridge,
                status="COMPLETED",
                defaults={"reason": "Step-down care and physiotherapy closer to home."}
            )

            # 6. Create Consents
            # Kwame grants FULL_RECORD to KBTH
            Consent.objects.get_or_create(
                global_patient=kwame,
                granted_to_facility=kbth,
                defaults={
                    "granted_by": kath_doc,
                    "scope": "FULL_RECORD",
                    "is_active": True,
                    "expires_at": timezone.now() + timezone.timedelta(days=365)
                }
            )

            # Kofi grants SUMMARY to Ridge
            Consent.objects.get_or_create(
                global_patient=kofi,
                granted_to_facility=ridge,
                defaults={
                    "granted_by": kath_doc,
                    "scope": "SUMMARY",
                    "is_active": True,
                    "expires_at": timezone.now() + timezone.timedelta(days=30)
                }
            )

            # 7. Create BreakGlassLog
            # Ridge doctor access Ama Serwaa (emergency)
            BreakGlassLog.objects.get_or_create(
                global_patient=ama,
                facility=ridge,
                accessed_by=ridge_doc,
                defaults={
                    "reason_code": "life_threatening_emergency",
                    "reason": "Patient brought in unconscious with multiple trauma. Immediate record access required for blood group and allergies.",
                    "expires_at": timezone.now() + timezone.timedelta(hours=4)
                }
            )

        self.stdout.write(self.style.SUCCESS("[DONE] Interop demo data seeded successfully!"))
