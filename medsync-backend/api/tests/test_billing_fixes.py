import pytest
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APIClient
from core.models import User, Hospital, AuditLog
from patients.models import Patient, Invoice, InvoiceItem

@pytest.fixture
def billing_client(db, hospital_a):
    """Create a billing staff user and authenticated API client."""
    user = User.objects.create_user(
        email="billing_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="billing_staff",
        hospital=hospital_a,
        account_status="active",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, hospital_a

@pytest.mark.django_db
def test_invoice_total_amount_property(patient_a, hospital_a, doctor_a):
    """Test that total_amount property correctly converts cents to GHS Decimal."""
    invoice = Invoice.objects.create(
        patient=patient_a,
        hospital=hospital_a,
        amount_cents=15050,  # 150.50 GHS
        currency="GHS",
        status="issued",
        created_by=doctor_a,
    )
    assert invoice.total_amount == Decimal("150.50")

@pytest.mark.django_db
def test_create_invoice_api_success(billing_client, patient_a):
    """Test creating an invoice with nested items through the API view."""
    client, user, hospital = billing_client
    
    data = {
        "patient_id": str(patient_a.id),
        "payment_method": "card",
        "notes": "Consultation and lab tests",
        "status": "issued",
        "items": [
            {
                "description": "General Consultation",
                "quantity": 1,
                "unit_price": 5000,
                "service_type": "consultation"
            },
            {
                "description": "Malaria Rapid Test",
                "quantity": 2,
                "unit_price": 2525,
                "service_type": "lab"
            }
        ]
    }
    
    response = client.post("/api/v1/billing/invoices/new", data, format="json")
    
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    res_data = response.json()
    assert res_data["patient_name"] == patient_a.full_name
    assert res_data["total_amount"] == 100.50  # 50.00 + (2 * 25.25)
    assert res_data["payment_method"] == "card"
    assert "invoice_number" in res_data
    assert res_data["invoice_number"] is not None
    
    # Verify DB records
    invoice = Invoice.objects.get(id=res_data["invoice_id"])
    assert invoice.amount_cents == 10050
    assert invoice.invoice_number == res_data["invoice_number"]
    assert invoice.items.count() == 2
    
    # Verify AuditLog has no NameError and logs correct patient info
    audit = AuditLog.objects.filter(action="INVOICE_CREATE").latest("timestamp")
    assert audit.resource_id == str(invoice.id)
    assert audit.extra_data["patient_id"] == str(patient_a.id)
    assert audit.extra_data["total_amount"] == 100.50
    assert audit.extra_data["payment_method"] == "card"
