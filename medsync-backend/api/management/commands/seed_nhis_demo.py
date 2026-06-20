"""
Management command: seed NHIS demo data for viva demonstration.

Usage:
    python manage.py seed_nhis_demo --hospital-id <uuid>

Creates 10 demo invoices with mixed payment methods and NHIS claim states
so the billing dashboard shows meaningful data during demonstration.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random

class Command(BaseCommand):
    help = "Seed NHIS billing demo data"

    def add_arguments(self, parser):
        parser.add_argument("--hospital-id", required=False, help="Hospital ID (defaults to Korle Bu GAC-001)")

    def handle(self, *args, **options):
        from core.models import Hospital, User
        from patients.models import Invoice, Patient
        
        hospital_id = options.get("hospital_id")
        if not hospital_id:
            hospital = Hospital.objects.filter(nhis_code="GAC-001").first()
            if not hospital:
                self.stderr.write("No default hospital (GAC-001) found. Run setup_dev first.")
                return
        else:
            try:
                hospital = Hospital.objects.get(id=hospital_id)
            except Hospital.DoesNotExist:
                self.stderr.write(f"Hospital with ID {hospital_id} does not exist.")
                return

        patients = Patient.objects.filter(registered_at=hospital)[:10]
        
        if not patients.exists():
            self.stderr.write("No patients found. Run seed_interop_demo first.")
            return

        # Find a user to attribute invoice creation to (created_by field)
        system_user = User.objects.filter(hospital=hospital).first() or User.objects.first()
        if not system_user:
            self.stderr.write("No users found. Please create a user/staff first.")
            return

        nhis_states = [
            ("submitted", f"NHIS-MOCK-{timezone.now().strftime('%Y%m%d')}-AA01"),
            ("approved", f"NHIS-MOCK-{timezone.now().strftime('%Y%m%d')}-BB02"),
            ("rejected", None),
            ("submitted", f"NHIS-MOCK-{timezone.now().strftime('%Y%m%d')}-CC03"),
            ("approved", f"NHIS-MOCK-{timezone.now().strftime('%Y%m%d')}-DD04"),
        ]
        
        created_count = 0
        for i, patient in enumerate(patients[:5]):
            state, ref = nhis_states[i]
            amount_val = random.randint(80, 650)
            amount_cents = amount_val * 100
            
            is_approved = (state == "approved")
            paid_amount = Decimal(amount_val) if is_approved else Decimal("0.00")
            paid_at = timezone.now() if is_approved else None
            
            Invoice.objects.create(
                patient=patient,
                hospital=hospital,
                invoice_number=f"INV-2406-{1000+i}",
                amount_cents=amount_cents,
                payment_method="nhis",
                status="paid" if is_approved else "pending",
                paid_amount=paid_amount,
                paid_at=paid_at,
                nhis_claim_status=state,
                nhis_claim_reference=ref,
                nhis_submitted_at=timezone.now() if ref else None,
                created_by=system_user,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"Created {created_count} NHIS demo invoices for {hospital.name}"
        ))
