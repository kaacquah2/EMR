"""
Revenue Cycle Management Views.

Handles billing, invoicing, NHIS claims, and payment processing.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital, User, AuditLog
from records.models import Prescription, LabOrder
from patients.models import Patient, Appointment, Invoice, InvoiceItem
from api.utils import get_request_hospital, sanitize_audit_resource_id
from api.pagination import paginate_queryset
from api.serializers import InvoiceCreateSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_dashboard(request):
    """
    Get billing dashboard metrics.
    
    Returns:
    - Today's revenue
    - Outstanding invoices
    - NHIS claims pending/approved
    - Revenue trends (weekly)
    """
    
    if request.user.role not in ('billing_staff', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    effective_hospital = get_request_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # Base queryset
    invoices = Invoice.objects.filter(hospital=effective_hospital)
    
    def _cents_to_decimal(qs, flt=Sum('amount_cents')):
        cents = qs.aggregate(total=flt)['total'] or 0
        return Decimal(str(cents)) / 100

    # Today's revenue (paid invoices)
    today_revenue = _cents_to_decimal(invoices.filter(status='paid', paid_at__gte=today_start))

    # Outstanding invoices (issued or partial)
    outstanding = invoices.filter(status__in=['issued', 'partial'])
    outstanding_count = outstanding.count()
    outstanding_amount = _cents_to_decimal(outstanding)

    # NHIS claims
    nhis_pending = invoices.filter(payment_method='nhis', nhis_claim_status='submitted').count()
    nhis_approved = invoices.filter(
        payment_method='nhis',
        nhis_claim_status='approved',
        created_at__gte=month_start
    ).count()
    nhis_rejected = invoices.filter(
        payment_method='nhis',
        nhis_claim_status='rejected',
        created_at__gte=month_start
    ).count()

    # Weekly revenue trend
    weekly_revenue = []
    for i in range(7):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_revenue = _cents_to_decimal(
            invoices.filter(status='paid', paid_at__gte=day_start, paid_at__lt=day_end)
        )
        weekly_revenue.append({
            'date': day_start.date().isoformat(),
            'revenue': float(day_revenue)
        })
    
    return Response({
        'today': {
            'revenue': float(today_revenue),
            'invoices_created': invoices.filter(created_at__gte=today_start).count(),
        },
        'outstanding': {
            'count': outstanding_count,
            'amount': float(outstanding_amount),
        },
        'nhis': {
            'pending': nhis_pending,
            'approved_this_month': nhis_approved,
            'rejected_this_month': nhis_rejected,
        },
        'weekly_trend': list(reversed(weekly_revenue)),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_invoice(request):
    """
    Create a new invoice for patient services.
    
    **Request body:**
    - patient_id: str (required)
    - items: list of {description, quantity, unit_price, service_type}
    - payment_method: str (cash|card|nhis|insurance)
    - notes: str (optional)
    """
    
    if request.user.role not in ('billing_staff', 'receptionist', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    effective_hospital = get_request_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Use Serializer for robust validation and nested creation
    data = request.data.copy()
    data["hospital"] = str(effective_hospital.id)
    if "patient_id" in data:
        data["patient"] = data["patient_id"]
    
    serializer = InvoiceCreateSerializer(data=data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        invoice = serializer.save()
        patient = invoice.patient
        
        # Audit log (Note: serializer handles nested items and total calculation)
        AuditLog.log_action(
            user=request.user,
            action='INVOICE_CREATE',
            resource_type='Invoice',
            resource_id=sanitize_audit_resource_id(str(invoice.id)),
            hospital=effective_hospital,
            extra_data={
                'patient_id': str(patient.id),
                'total_amount': float(invoice.total_amount),
                'payment_method': invoice.payment_method,
            }
        )
        
        return Response({
            'invoice_id': str(invoice.id),
            'invoice_number': invoice.invoice_number if hasattr(invoice, 'invoice_number') else str(invoice.id)[:8].upper(),
            'patient_name': patient.full_name,
            'total_amount': float(invoice.total_amount),
            'payment_method': invoice.payment_method,
            'status': invoice.status,
            'created_at': invoice.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Invoice creation failed: {str(e)}")
        return Response({"error": "Failed to create invoice."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_payment(request, invoice_id):
    """
    Record a payment against an invoice.
    
    **Request body:**
    - amount: decimal (required)
    - payment_reference: str (optional, for card/transfer)
    - notes: str (optional)
    """
    
    if request.user.role not in ('billing_staff', 'receptionist', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    if invoice_id is None:
        return Response({'error': 'invoice_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get payment amount
    amount = request.data.get('amount')
    if not amount:
        return Response({'error': 'amount is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return Response({'error': 'amount must be a positive number'}, status=status.HTTP_400_BAD_REQUEST)
    
    payment_reference = request.data.get('payment_reference', '')
    notes = request.data.get('notes', '')
    
    effective_hospital = get_request_hospital(request)

    with transaction.atomic():
        try:
            # HIGH-5 FIX: Use select_for_update() with atomic transaction to prevent race conditions
            invoice = Invoice.objects.select_for_update().select_related('patient', 'hospital').get(pk=invoice_id)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if effective_hospital and invoice.hospital_id != effective_hospital.id:
            return Response({'error': 'Cannot process payment for another hospital'}, status=status.HTTP_403_FORBIDDEN)
        
        if invoice.status == 'paid':
            return Response({'error': 'Invoice already fully paid'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate new paid amount
        current_paid = invoice.paid_amount if hasattr(invoice, 'paid_amount') and invoice.paid_amount else Decimal('0.00')
        new_paid = current_paid + amount

        # Update invoice — use model choices: 'paid' or 'partial'
        if new_paid >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
        else:
            invoice.status = 'partial'
        
        if hasattr(invoice, 'paid_amount'):
            invoice.paid_amount = new_paid
        
        if payment_reference and hasattr(invoice, 'payment_reference'):
            invoice.payment_reference = payment_reference
            
        invoice.save()
        
        # Audit log
        AuditLog.log_action(
            user=request.user,
            action='PAYMENT_RECORD',
            resource_type='Invoice',
            resource_id=sanitize_audit_resource_id(str(invoice.id)),
            hospital=invoice.hospital,
            extra_data={
                'amount': float(amount),
                'payment_reference': payment_reference,
                'new_status': invoice.status,
            }
        )
    
    return Response({
        'invoice_id': str(invoice.id),
        'amount_paid': float(amount),
        'total_paid': float(new_paid),
        'total_amount': float(invoice.total_amount),
        'remaining': float(invoice.total_amount - new_paid),
        'status': invoice.status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_nhis_claim(request, invoice_id):
    """
    Submit an invoice to NHIS for claim processing.

    Calls the Ghana NHIA API to:
    1. Verify patient eligibility (NHISClient.check_eligibility)
    2. Submit the claim (NHISClient.submit_claim)

    Falls back to offline mode (mock reference) when NHIS_API_KEY is not
    configured (development / staging environments).

    **Request body:**
    - nhis_member_id: str (patient's NHIS card number)
    - diagnosis_codes: list of ICD-10 codes (e.g. ["A09", "I10"])
    - check_eligibility: bool (default: true — verify card before submitting)
    - notes: str (optional)
    """
    from api.integrations.nhis_client import (
        get_nhis_client, NHISClaimItem,
        NHISRetryableError, NHISClaimError, NHISCircuitOpenError,
    )

    if request.user.role not in ('billing_staff', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

    try:
        invoice = Invoice.objects.select_related('patient', 'hospital').get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)

    effective_hospital = get_request_hospital(request)
    if effective_hospital and invoice.hospital_id != effective_hospital.id:
        return Response({'error': 'Cannot submit claim for another hospital'}, status=status.HTTP_403_FORBIDDEN)

    if invoice.payment_method != 'nhis':
        return Response({'error': 'Invoice payment method must be NHIS'}, status=status.HTTP_400_BAD_REQUEST)

    if hasattr(invoice, 'nhis_claim_status') and invoice.nhis_claim_status in ('submitted', 'approved'):
        return Response({'error': f'Claim already {invoice.nhis_claim_status}'}, status=status.HTTP_400_BAD_REQUEST)

    # --- Input validation ---
    nhis_member_id = (request.data.get('nhis_member_id') or '').strip()
    diagnosis_codes = request.data.get('diagnosis_codes', [])
    should_check_eligibility = request.data.get('check_eligibility', True)

    if not nhis_member_id:
        return Response({'error': 'nhis_member_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(diagnosis_codes, list) or len(diagnosis_codes) == 0:
        return Response({'error': 'diagnosis_codes must be a non-empty list of ICD-10 codes'},
                        status=status.HTTP_400_BAD_REQUEST)

    nhis_client = get_nhis_client()

    # --- Step 1: Eligibility check (optional but strongly recommended) ---
    eligibility = None
    if should_check_eligibility:
        try:
            eligibility = nhis_client.check_eligibility(nhis_member_id)
            if not eligibility.is_eligible:
                return Response({
                    'error': f"Patient NHIS card is not eligible: {eligibility.card_status}",
                    'card_status': eligibility.card_status,
                    'card_expiry_date': eligibility.card_expiry_date.isoformat() if eligibility.card_expiry_date else None,
                }, status=status.HTTP_400_BAD_REQUEST)
        except NHISCircuitOpenError as e:
            logger.warning("NHIS circuit open during eligibility check: %s", e)
            # Proceed without eligibility check — don't block care delivery
            pass
        except NHISRetryableError as e:
            logger.warning("NHIS eligibility check transient error: %s", e)
            # Proceed without eligibility check
            pass
        except NHISClaimError as e:
            return Response({'error': f'NHIS eligibility check failed: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    # --- Step 2: Build claim items from invoice line items ---
    claim_items = []
    invoice_items = getattr(invoice, 'items', None)
    if invoice_items is not None:
        for item in invoice_items.all():
            claim_items.append(NHISClaimItem(
                service_code=getattr(item, 'nhis_service_code', None) or getattr(item, 'service_type', 'CONSULT'),
                description=item.description,
                quantity=item.quantity,
                unit_price_ghs=Decimal(str(item.unit_price / 100)),  # stored in cents
            ))

    # Fallback: single aggregate claim item
    if not claim_items:
        claim_items.append(NHISClaimItem(
            service_code="CONSULT",
            description="Medical Services",
            quantity=1,
            unit_price_ghs=getattr(invoice, 'total_amount', Decimal('0.00')),
        ))

    # --- Step 3: Submit claim ---
    try:
        result = nhis_client.submit_claim(
            invoice_id=str(invoice.id),
            nhis_member_id=nhis_member_id,
            diagnosis_codes=diagnosis_codes,
            items=claim_items,
            attending_provider_id=getattr(request.user, 'gmdc_licence_number', None),
        )

        # Persist claim reference on invoice
        with transaction.atomic():
            if hasattr(invoice, 'nhis_claim_status'):
                invoice.nhis_claim_status = 'submitted'
            if hasattr(invoice, 'nhis_claim_reference'):
                invoice.nhis_claim_reference = result.claim_reference
            if hasattr(invoice, 'nhis_submitted_at'):
                invoice.nhis_submitted_at = timezone.now()
            invoice.save()

            AuditLog.log_action(
                user=request.user,
                action='NHIS_CLAIM_SUBMIT',
                resource_type='Invoice',
                resource_id=sanitize_audit_resource_id(str(invoice.id)),
                hospital=invoice.hospital,
                extra_data={
                    'claim_reference': result.claim_reference,
                    'nhis_status': result.status,
                    'item_count': len(claim_items),
                }
            )

        return Response({
            'invoice_id': str(invoice.id),
            'claim_reference': result.claim_reference,
            'nhis_status': result.status,
            'submitted_at': result.submitted_at.isoformat() if result.submitted_at else timezone.now().isoformat(),
            'eligibility': {
                'card_status': eligibility.card_status if eligibility else 'NOT_CHECKED',
                'benefit_package': eligibility.benefit_package if eligibility else None,
                'exemption': eligibility.exemption_message if eligibility else None,
            },
            'message': 'NHIS claim submitted successfully. Allow 24-48 hours for processing.',
        })

    except NHISCircuitOpenError as e:
        logger.error("NHIS circuit open during claim submission: %s", e)
        return Response({
            'error': 'NHIS API is temporarily unavailable. Claim has been queued for retry.',
            'retry_available': True,
        }, status=status.HTTP_202_ACCEPTED)

    except NHISRetryableError as e:
        logger.error("NHIS claim submission transient error: %s", e)
        return Response({
            'error': f'NHIS service temporarily unavailable: {e}. Please retry shortly.',
            'retry_available': True,
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except NHISClaimError as e:
        logger.warning("NHIS claim rejected: %s (code: %s)", e, e.error_code)
        return Response({
            'error': f'NHIS rejected claim: {e}',
            'nhis_error_code': e.error_code,
            'retry_available': False,
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception("Unexpected error during NHIS claim submission: %s", e)
        return Response({'error': 'Internal error during claim submission.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_billing_history(request, patient_id):
    """
    Get billing history for a patient.
    """
    
    if request.user.role not in ('billing_staff', 'receptionist', 'doctor', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
    
    effective_hospital = get_request_hospital(request)
    
    # Get invoices
    invoices_qs = Invoice.objects.filter(patient=patient)
    if effective_hospital:
        invoices_qs = invoices_qs.filter(hospital=effective_hospital)
    
    invoices_qs = invoices_qs.order_by('-created_at')
    
    items, next_cursor, has_more = paginate_queryset(invoices_qs, request)
    
    invoices = []
    for inv in items:
        invoices.append({
            'invoice_id': str(inv.id),
            'created_at': inv.created_at.isoformat(),
            'total_amount': float(inv.total_amount),
            'status': inv.status,
            'payment_method': inv.payment_method,
            'paid_at': inv.paid_at.isoformat() if inv.paid_at else None,
        })
    
    # Summary
    def _sum_cents(qs):
        cents = qs.aggregate(total=Sum('amount_cents'))['total'] or 0
        return Decimal(str(cents)) / 100

    total_billed = _sum_cents(invoices_qs)
    total_paid = _sum_cents(invoices_qs.filter(status='paid'))
    outstanding = _sum_cents(invoices_qs.filter(status__in=['issued', 'partial']))
    
    return Response({
        'patient_id': str(patient.id),
        'patient_name': patient.full_name,
        'summary': {
            'total_billed': float(total_billed),
            'total_paid': float(total_paid),
            'outstanding': float(outstanding),
            'invoice_count': invoices_qs.count(),
        },
        'invoices': invoices,
        'next_cursor': next_cursor,
        'has_more': has_more,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def nhis_integration_status(request):
    """
    NHIS integration health check.
    Returns current mode (mock/live), circuit breaker state,
    and configuration status. Safe to call from admin dashboard.
    """
    if request.user.role not in ("billing_staff", "hospital_admin", "super_admin"):
        return Response({"error": "Forbidden"}, status=403)
    
    from django.conf import settings
    from api.integrations.nhis_client import NHISClient
    client = NHISClient()
    
    is_configured = client._is_configured()
    cb = NHISClient._circuit_breaker
    
    return Response({
        "mode": "live" if is_configured else "mock",
        "configured": is_configured,
        "circuit_breaker": {
            "state": cb.state if cb else "CLOSED",
            "description": (
                "NHIS API requests are passing normally"
                if (not cb or cb.state == "CLOSED")
                else "NHIS API is unavailable — claims queued for retry"
            ),
        },
        "nhia_api_base": getattr(settings, "NHIS_API_BASE_URL", "") or "Not configured",
        "facility_code": getattr(settings, "NHIS_FACILITY_CODE", "") or "Not configured",
        "mock_note": (
            None if is_configured else
            "Running in offline/mock mode. Set NHIS_API_BASE_URL, "
            "NHIS_API_KEY, and NHIS_FACILITY_CODE to connect to the "
            "Ghana National Health Insurance Authority (NHIA) API. "
            "Claim references are generated locally with prefix NHIS-MOCK-."
        ),
    })
