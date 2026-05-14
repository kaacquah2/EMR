"""
Django management command to load synthetic patient data from JSON.

Usage:
    python manage.py load_demo_patients --file=demo_patients.json --hospital-id=<id>
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from patients.models import Patient, Allergy
from records.models import Encounter, MedicalRecord, Diagnosis, Prescription, Vital
from core.models import Hospital, User


class Command(BaseCommand):
    help = "Load synthetic patient data from JSON into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/seeds/demo_patients.json",
            help="Path to the generated JSON file (default: data/seeds/demo_patients.json)"
        )
        parser.add_argument(
            "--hospital-id",
            type=str,
            help="Hospital UUID to load data for. If not provided, uses first active hospital."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing patients before loading (optional)"
        )

    def handle(self, *args, **options):
        try:
            with open(options["file"], "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['file']}")
        except json.JSONDecodeError:
            raise CommandError(f"Invalid JSON in file: {options['file']}")

        # Determine hospital
        if options["hospital_id"]:
            try:
                hospital = Hospital.objects.get(id=options["hospital_id"])
            except Hospital.DoesNotExist:
                raise CommandError(f"Hospital not found: {options['hospital_id']}")
        else:
            hospital = Hospital.objects.filter(is_active=True).first()
            if not hospital:
                raise CommandError("No active hospital found. Please specify --hospital-id or create a hospital.")

        # Get a system user for created_by (use first admin or create)
        system_user = User.objects.filter(role="super_admin").first()
        if not system_user:
            system_user = User.objects.filter(role="hospital_admin", hospital=hospital).first()
        if not system_user:
            raise CommandError("No admin user found. Please create a hospital admin first.")

        self.stdout.write(f"📥 Loading {len(data['patients'])} patients to {hospital.name}...")

        if options["clear"]:
            self.stdout.write(self.style.WARNING("⚠️  Clearing existing patients..."))
            Patient.objects.filter(registered_at=hospital).delete()

        loaded_count = 0
        error_count = 0

        with transaction.atomic():
            for patient_data in data["patients"]:
                try:
                    loaded_count += self._load_patient(
                        patient_data, hospital, system_user
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error loading {patient_data.get('ghana_health_id')}: {str(e)}")
                    )
                    error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Loaded {loaded_count} patients (errors: {error_count})"
            )
        )

    def _load_patient(self, patient_data: dict, hospital: Hospital, system_user: User) -> int:
        """Load a single patient and their encounters."""
        # Create patient
        patient = Patient.objects.create(
            ghana_health_id=patient_data["ghana_health_id"],
            full_name=patient_data["full_name"],
            date_of_birth=datetime.strptime(
                patient_data["date_of_birth"], "%Y-%m-%d"
            ).date(),
            gender=patient_data["gender"],
            phone=patient_data.get("phone", ""),
            blood_group=patient_data.get("blood_group", "unknown"),
            registered_at=hospital,
            created_by=system_user,
        )

        # Add allergies
        for allergy_name in patient_data.get("allergies", []):
            Allergy.objects.create(
                patient=patient,
                allergen=allergy_name,
                reaction_type="Unknown",
                severity="moderate",
                recorded_by=system_user,
            )

        # Load encounters
        for encounter_data in patient_data.get("encounters", []):
            self._load_encounter(encounter_data, patient, hospital, system_user)

        return 1

    def _load_encounter(
        self, encounter_data: dict, patient: Patient, hospital: Hospital, system_user: User
    ):
        """Load a single encounter with vitals, diagnoses, and prescriptions."""
        # Parse encounter date/time
        encounter_datetime = datetime.strptime(
            f"{encounter_data['date']} {encounter_data['time']}", "%Y-%m-%d %H:%M"
        )

        # Create encounter
        encounter = Encounter.objects.create(
            patient=patient,
            hospital=hospital,
            provider=system_user,
            encounter_type=encounter_data.get("encounter_type", "clinic"),
            chief_complaint=encounter_data.get("chief_complaint", ""),
            encounter_date=encounter_datetime,
            created_by=system_user,
        )

        # Load vitals
        vitals_data = encounter_data.get("vitals", {})
        if vitals_data:
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="vital_signs",
                created_by=system_user,
            )
            Vital.objects.create(
                record=record,
                patient=patient,
                hospital=hospital,
                temperature=vitals_data.get("temperature_celsius"),
                systolic_bp=vitals_data.get("systolic_bp"),
                diastolic_bp=vitals_data.get("diastolic_bp"),
                heart_rate=vitals_data.get("heart_rate"),
                respiratory_rate=vitals_data.get("respiratory_rate"),
                spo2=vitals_data.get("spo2_percent"),
                created_by=system_user,
            )

        # Load diagnoses
        for diagnosis_data in encounter_data.get("diagnoses", []):
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="diagnosis",
                created_by=system_user,
            )
            Diagnosis.objects.create(
                record=record,
                icd10_code=diagnosis_data.get("icd10_code"),
                icd10_description=diagnosis_data.get("description", ""),
                severity=diagnosis_data.get("severity", "mild"),
                is_chronic=diagnosis_data.get("is_chronic", False),
            )

        # Load prescriptions
        for prescription_data in encounter_data.get("prescriptions", []):
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="prescription",
                created_by=system_user,
            )
            Prescription.objects.create(
                record=record,
                patient=patient,
                hospital=hospital,
                drug_name=prescription_data.get("drug_name", ""),
                dosage=prescription_data.get("dosage", ""),
                frequency=prescription_data.get("frequency", ""),
                duration_days=prescription_data.get("duration_days"),
                route=prescription_data.get("route", "oral"),
                status="pending",
            )
