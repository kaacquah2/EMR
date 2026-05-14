"""
Pharmacy stock and dispensation API endpoints.

Endpoints:
- GET/POST /pharmacy/stock/ — list and add stock
- GET /pharmacy/stock/<id>/ — stock detail with movement history
- POST /pharmacy/stock/<id>/adjust/ — manual adjustment with reason
- GET /pharmacy/dispensations/?patient=<id> — dispensation history
- GET /pharmacy/reports/low-stock/ — items below reorder level
- GET /pharmacy/reports/expiring/ — items expiring within 30 days
- POST /pharmacy/prescriptions/<id>/dispense-confirm/ — change prescription to dispensed
- POST /pharmacy/tasks/check-expiry/ — manual trigger for expiry check

All endpoints include permission checks and hospital scoping.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital, AuditLog
from api.models import DrugStock, Dispensation, StockMovement, StockAlert
from records.models import Prescription
from patients.models import Patient
from api.utils import get_effective_hospital, sanitize_audit_resource_id
from api.permissions_helpers import can_access_patient
from api.tasks.pharmacy_tasks import check_expiring_stock_task

logger = logging.getLogger(__name__)


def _is_pharmacy_staff(user):
    """Check if user can access pharmacy (pharmacy_technician or hospital_admin or super_admin)."""
    return user.role in ['pharmacy_technician', 'hospital_admin', 'super_admin']


def _can_dispense(user):
    """Check if user can dispense (pharmacy_technician or super_admin only)."""
    return user.role in ['pharmacy_technician', 'super_admin']


def _can_adjust_stock(user):
    """Check if user can manually adjust stock (pharmacy_technician or super_admin)."""
    return user.role in ['pharmacy_technician', 'super_admin']


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def stock_list_create(request):
    """
    GET: List drug stock (filterable by drug_name, low_stock status)
    POST: Add new batch
    
    Query params:
    - drug_name: filter by drug name (substring match)
    - low_stock: "true" to show only below reorder level
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'GET':
        # List stock
        qs = DrugStock.objects.filter(hospital=hospital)
        
        # Filter by drug_name
        drug_name = request.GET.get('drug_name')
        if drug_name:
            qs = qs.filter(drug_name__icontains=drug_name)
        
        # Filter by low_stock
        if request.GET.get('low_stock') == 'true':
            qs = qs.filter(quantity__lt=F('reorder_level'))
        
        # Ordering
        qs = qs.order_by('-created_at')
        
        items = list(qs.values(
            'id', 'drug_name', 'generic_name', 'batch_number', 'quantity', 'unit',
            'reorder_level', 'expiry_date', 'created_at'
        ))
        
        return Response({
            'count': len(items),
            'results': items
        })
    
    elif request.method == 'POST':
        # Add new batch
        data = request.data
        
        required_fields = ['drug_name', 'batch_number', 'quantity', 'unit', 'reorder_level', 'expiry_date']
        missing = [f for f in required_fields if f not in data or not data[f]]
        if missing:
            return Response(
                {'error': f'Missing required fields: {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stock = DrugStock.objects.create(
                hospital=hospital,
                drug_name=data['drug_name'],
                generic_name=data.get('generic_name', ''),
                batch_number=data['batch_number'],
                quantity=int(data['quantity']),
                unit=data['unit'],
                reorder_level=int(data['reorder_level']),
                expiry_date=data['expiry_date']
            )
            
            # Create stock movement record
            StockMovement.objects.create(
                drug_stock=stock,
                movement_type='received',
                quantity=stock.quantity,
                reason='Initial stock received',
                performed_by=request.user
            )
            
            # Audit log
            AuditLog.log_action(
                user=request.user,
                action='ADD_DRUG_STOCK',
                resource_type='DrugStock',
                resource_id=str(stock.id),
                hospital=hospital,
                extra_data={
                    'drug': stock.drug_name,
                    'batch': stock.batch_number,
                    'quantity': stock.quantity,
                    'expiry': str(stock.expiry_date),
                }
            )
            
            return Response({
                'id': str(stock.id),
                'drug_name': stock.drug_name,
                'batch_number': stock.batch_number,
                'quantity': stock.quantity,
                'unit': stock.unit,
                'reorder_level': stock.reorder_level,
                'expiry_date': stock.expiry_date,
                'created_at': stock.created_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error adding stock: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_detail(request, stock_id):
    """
    Get stock detail with movement history.
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        stock = DrugStock.objects.get(id=stock_id, hospital=hospital)
    except DrugStock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
    
    movements = list(StockMovement.objects.filter(drug_stock=stock).order_by('-created_at').values(
        'id', 'movement_type', 'quantity', 'reason', 'performed_by__full_name', 'created_at'
    ))
    
    return Response({
        'id': str(stock.id),
        'drug_name': stock.drug_name,
        'generic_name': stock.generic_name,
        'batch_number': stock.batch_number,
        'quantity': stock.quantity,
        'unit': stock.unit,
        'reorder_level': stock.reorder_level,
        'expiry_date': stock.expiry_date,
        'is_expired': stock.is_expired(),
        'days_until_expiry': stock.days_until_expiry(),
        'is_low_stock': stock.is_low_stock(),
        'movements': movements,
        'created_at': stock.created_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def adjust_stock(request, stock_id):
    """
    Manually adjust stock with reason (hospital_admin + pharmacy_technician only).
    
    Request body:
    {
        "quantity_change": -5,  // negative for removal, positive for addition
        "reason": "Damaged units removed",
        "movement_type": "damaged"  // or "adjustment"
    }
    """
    if not _can_adjust_stock(request.user):
        if request.user.role != 'hospital_admin':
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        stock = DrugStock.objects.get(id=stock_id, hospital=hospital)
    except DrugStock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
    
    data = request.data
    if 'quantity_change' not in data or 'reason' not in data:
        return Response(
            {'error': 'Missing quantity_change or reason'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        qty_change = int(data['quantity_change'])
        reason = str(data['reason']).strip()
        movement_type = data.get('movement_type', 'adjustment')
        
        if not reason:
            return Response(
                {'error': 'Reason cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            stock.quantity += qty_change
            if stock.quantity < 0:
                stock.quantity = 0
            stock.save(update_fields=['quantity'])
            
            # Create movement record
            movement = StockMovement.objects.create(
                drug_stock=stock,
                movement_type=movement_type,
                quantity=qty_change,
                quantity_before=stock.quantity - qty_change,  # Before the change
                quantity_after=stock.quantity,  # After the change
                reason=reason,
                performed_by=request.user
            )
            
            # Audit log
            AuditLog.log_action(
                user=request.user,
                action='ADJUST_STOCK',
                resource_type='DrugStock',
                resource_id=str(stock.id),
                hospital=hospital,
                extra_data={
                    'drug': stock.drug_name,
                    'batch': stock.batch_number,
                    'change': qty_change,
                    'reason': reason,
                }
            )
            
            return Response({
                'id': str(stock.id),
                'quantity': stock.quantity,
                'movement_id': str(movement.id),
                'message': f'Stock adjusted by {qty_change} units'
            })
    
    except ValueError:
        return Response(
            {'error': 'quantity_change must be an integer'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error adjusting stock: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dispensation_list(request):
    """
    Get dispensation history, filterable by patient.
    
    Query params:
    - patient_id: filter by patient UUID
    - drug_name: filter by drug name
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Filter by hospital (via drug_stock)
    qs = Dispensation.objects.filter(
        drug_stock__hospital=hospital
    ).order_by('-dispensed_at').select_related('drug_stock', 'prescription', 'dispensed_by')
    
    # Filter by patient
    patient_id = request.GET.get('patient_id')
    if patient_id:
        qs = qs.filter(prescription__patient_id=patient_id)
    
    # Filter by drug_name
    drug_name = request.GET.get('drug_name')
    if drug_name:
        qs = qs.filter(drug_stock__drug_name__icontains=drug_name)
    
    results = []
    for d in qs:
        results.append({
            'id': str(d.id),
            'prescription_id': str(d.prescription.id),
            'patient_id': str(d.prescription.patient_id) if d.prescription.patient else None,
            'patient_name': d.prescription.patient.full_name if d.prescription.patient else None,
            'drug_name': d.drug_stock.drug_name,
            'batch_number': d.drug_stock.batch_number,
            'quantity_dispensed': d.quantity_dispensed,
            'unit': d.drug_stock.unit,
            'dispensed_by': d.dispensed_by.full_name,
            'dispensed_at': d.dispensed_at.isoformat(),
            'notes': d.batch_notes,
        })
    
    return Response({
        'count': len(results),
        'results': results
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_report(request):
    """
    List all drug stock items below reorder level.
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    low_stock = DrugStock.objects.filter(
        hospital=hospital,
        quantity__lt=F('reorder_level'),
        expiry_date__gt=timezone.now().date()
    ).order_by('-created_at')
    
    results = []
    for stock in low_stock:
        results.append({
            'id': str(stock.id),
            'drug_name': stock.drug_name,
            'batch_number': stock.batch_number,
            'current_quantity': stock.quantity,
            'reorder_level': stock.reorder_level,
            'unit': stock.unit,
            'shortage': stock.reorder_level - stock.quantity,
            'expiry_date': stock.expiry_date.isoformat(),
        })
    
    return Response({
        'count': len(results),
        'results': results
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_stock_report(request):
    """
    List all drug stock expiring within 30 days.
    
    Query params:
    - days: number of days to look ahead (default 30)
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    days = int(request.GET.get('days', 30))
    cutoff = timezone.now().date() + timedelta(days=days)
    
    expiring = DrugStock.objects.filter(
        hospital=hospital,
        expiry_date__lte=cutoff,
        expiry_date__gt=timezone.now().date(),
        quantity__gt=0
    ).order_by('expiry_date')
    
    results = []
    for stock in expiring:
        days_to_expiry = (stock.expiry_date - timezone.now().date()).days
        results.append({
            'id': str(stock.id),
            'drug_name': stock.drug_name,
            'batch_number': stock.batch_number,
            'quantity': stock.quantity,
            'unit': stock.unit,
            'expiry_date': stock.expiry_date.isoformat(),
            'days_to_expiry': days_to_expiry,
            'is_critical': days_to_expiry <= 7,
        })
    
    return Response({
        'count': len(results),
        'results': results
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_expiry_manual_trigger(request):
    """
    Manually trigger the expiry check task.
    """
    if not _is_pharmacy_staff(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Queue the task
        task = check_expiring_stock_task.delay()
        
        return Response({
            'message': 'Expiry check queued',
            'task_id': task.id,
        })
    except Exception as e:
        logger.error(f"Error queuing expiry check: {e}")
        return Response(
            {'error': 'Failed to queue task'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dispense_confirm(request, prescription_id):
    """
    Confirm dispensation: change prescription from dispensing → dispensed.
    
    Request body (optional):
    {
        "drug_stock_id": "uuid",  // Custom batch selection (optional, uses FIFO if omitted)
        "quantity": 1,            // Qty to dispense (optional, defaults to 1)
        "notes": "Patient counseled"
    }
    
    This triggers auto-deduction via signals.
    """
    if not _can_dispense(request.user):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        prescription = Prescription.objects.get(id=prescription_id, hospital=hospital)
    except Prescription.DoesNotExist:
        return Response({'error': 'Prescription not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if prescription.status != 'dispensing':
        return Response(
            {'error': f'Prescription status must be "dispensing", not "{prescription.status}"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        data = request.data
        quantity = int(data.get('quantity', 1))
        if quantity <= 0:
            return Response(
                {'error': 'Quantity must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Update prescription
            prescription.status = 'dispensed'
            prescription.dispensed_by = request.user
            prescription.dispensed_quantity = quantity
            prescription.dispense_notes = data.get('notes', '')
            prescription.save(update_fields=[
                'status', 'dispensed_by', 'dispensed_quantity', 'dispense_notes'
            ])
            
            # Audit log
            AuditLog.log_action(
                user=request.user,
                action='DISPENSE_PRESCRIPTION',
                resource_type='Prescription',
                resource_id=str(prescription.id),
                hospital=hospital,
                extra_data={
                    'drug': prescription.drug_name,
                    'patient_id': str(prescription.patient.id) if prescription.patient else None,
                    'quantity': quantity,
                }
            )
            
            # Signal will trigger auto-deduction
            return Response({
                'id': str(prescription.id),
                'status': 'dispensed',
                'message': 'Prescription dispensed successfully'
            })
    
    except ValueError as e:
        return Response(
            {'error': f'Invalid input: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error dispensing prescription: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

