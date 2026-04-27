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
from api.utils import get_effective_hospital, sanitize_audit_resource_id
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
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # Base queryset
    invoices = Invoice.objects.filter(hospital=effective_hospital)
    
    # Today's revenue (paid invoices)
    today_revenue = invoices.filter(
        status='paid',
        paid_at__gte=today_start
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Outstanding invoices
    outstanding = invoices.filter(status__in=['pending', 'partially_paid'])
    outstanding_count = outstanding.count()
    outstanding_amount = outstanding.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
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
        day_revenue = invoices.filter(
            status='paid',
            paid_at__gte=day_start,
            paid_at__lt=day_end
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
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
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Use Serializer for robust validation and nested creation
    data = request.data.copy()
    data["hospital"] = str(effective_hospital.id)
    
    serializer = InvoiceCreateSerializer(data=data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        invoice = serializer.save()
        
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
    
    effective_hospital = get_effective_hospital(request)

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
        
        # Update invoice
        if new_paid >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
        else:
            invoice.status = 'partially_paid'
        
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
    
    **Request body:**
    - nhis_member_id: str (patient's NHIS number)
    - diagnosis_codes: list of ICD-10 codes
    - notes: str (optional)
    """
    
    if request.user.role not in ('billing_staff', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        invoice = Invoice.objects.select_related('patient', 'hospital').get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
    
    effective_hospital = get_effective_hospital(request)
    if effective_hospital and invoice.hospital_id != effective_hospital.id:
        return Response({'error': 'Cannot submit claim for another hospital'}, status=status.HTTP_403_FORBIDDEN)
    
    if invoice.payment_method != 'nhis':
        return Response({'error': 'Invoice payment method must be NHIS'}, status=status.HTTP_400_BAD_REQUEST)
    
    if hasattr(invoice, 'nhis_claim_status') and invoice.nhis_claim_status in ('submitted', 'approved'):
        return Response({'error': f'Claim already {invoice.nhis_claim_status}'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get claim data
    nhis_member_id = request.data.get('nhis_member_id')
    diagnosis_codes = request.data.get('diagnosis_codes', [])
    
    if not nhis_member_id:
        return Response({'error': 'nhis_member_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # In production, this would call NHIS API
    # For now, simulate submission
    claim_reference = f"NHIS-{timezone.now().strftime('%Y%m%d')}-{str(invoice.id)[:8].upper()}"
    
    with transaction.atomic():
        if hasattr(invoice, 'nhis_claim_status'):
            invoice.nhis_claim_status = 'submitted'
        if hasattr(invoice, 'nhis_claim_reference'):
            invoice.nhis_claim_reference = claim_reference
        if hasattr(invoice, 'nhis_submitted_at'):
            invoice.nhis_submitted_at = timezone.now()
        invoice.save()
        
        # Audit log
        AuditLog.log_action(
            user=request.user,
            action='NHIS_CLAIM_SUBMIT',
            resource_type='Invoice',
            resource_id=sanitize_audit_resource_id(str(invoice.id)),
            hospital=invoice.hospital,
            extra_data={
                'claim_reference': claim_reference,
                'nhis_member_id': nhis_member_id,
                'total_amount': float(invoice.total_amount),
            }
        )
    
    return Response({
        'invoice_id': str(invoice.id),
        'claim_reference': claim_reference,
        'status': 'submitted',
        'submitted_at': timezone.now().isoformat(),
        'message': 'NHIS claim submitted successfully. Allow 24-48 hours for processing.',
    })


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
    
    effective_hospital = get_effective_hospital(request)
    
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
    total_billed = invoices_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_paid = invoices_qs.filter(status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    outstanding = invoices_qs.filter(status__in=['pending', 'partially_paid']).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
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
