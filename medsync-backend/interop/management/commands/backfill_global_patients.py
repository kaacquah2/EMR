from django.core.management.base import BaseCommand
from patients.models import Patient
from interop.models import GlobalPatient, FacilityPatient


class Command(BaseCommand):
    help = "Create GlobalPatient and FacilityPatient for each existing Patient (backfill)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be done.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("Dry run: no changes will be made.")

        created_gp = 0
        created_fp = 0
        skipped = 0

        for patient in Patient.objects.select_related("registered_at").iterator():
            # Use ghana_health_id as national_id for global identity
            national_id = patient.ghana_health_id or None
            parts = (patient.full_name or "Unknown").strip().split(None, 1)
            first_name = parts[0] if parts else "Unknown"
            last_name = parts[1] if len(parts) > 1 else ""

            gp = None
            if national_id:
                gp = GlobalPatient.objects.filter(national_id=national_id).first()
            if not gp:
                # Create GlobalPatient
                if not dry_run:
                    gp = GlobalPatient.objects.create(
                        national_id=national_id,
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=patient.date_of_birth,
                        gender=patient.gender,
                        blood_group=patient.blood_group or "unknown",
                        phone=patient.phone,
                        email=None,
                    )
                    created_gp += 1
                else:
                    created_gp += 1
                    continue
            else:
                skipped += 1

            if not gp:
                continue

            existing = FacilityPatient.objects.filter(
                facility=patient.registered_at,
                global_patient=gp,
                deleted_at__isnull=True,
            ).first()
            if existing:
                if not dry_run and not existing.patient_id:
                    existing.patient = patient
                    existing.local_patient_id = str(patient.id)
                    existing.save(update_fields=["patient", "local_patient_id", "updated_at"])
                    created_fp += 1
                continue
            if not dry_run:
                FacilityPatient.objects.create(
                    facility=patient.registered_at,
                    global_patient=gp,
                    local_patient_id=str(patient.id),
                    patient=patient,
                )
                created_fp += 1
            else:
                created_fp += 1

        self.stdout.write(
            f"GlobalPatients created: {created_gp}, FacilityPatients created: {created_fp}, skipped (existing GP): {skipped}"
        )
