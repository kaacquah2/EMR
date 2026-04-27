"""
Batch Operations Views.

Handles bulk user imports, bulk invitations, and batch operation tracking.

Endpoints:
- GET /batch-operations/summary — Batch operations dashboard summary
- POST /batch-import — Start new batch import
- GET /batch-import/{job_id} — Get import status and details
- POST /batch-import/{job_id}/items — Get items with pagination
- GET /batch-import/{job_id}/export — Export results as CSV
- POST /bulk-invitations — Create bulk invitation campaign
- GET /bulk-invitations/{campaign_id} — Get campaign details
- POST /bulk-invitations/{campaign_id}/send — Send pending invitations
- GET /bulk-invitations/expiration-check — Check expiring invitations
"""

import csv
from datetime import timedelta
from io import StringIO

from django.utils import timezone
from django.db.models import Q, Count, Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import User, Ward, Hospital, AuditLog
from api.batch_models import (
    BatchImportJob, BatchImportItem,
    BulkInvitationJob, BulkInvitationItem
)
from api.utils import get_request_hospital, sanitize_audit_resource_id, get_effective_hospital


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_operations_summary(request):
    """
    Get summary of all batch operations (imports and campaigns).
    
    For super_admin: returns aggregated stats across all hospitals
    For hospital_admin: returns stats for their hospital only
    
    Returns:
    {
        "import_jobs": {
            "total": 10,
            "active": 2,
            "completed": 7,
            "failed": 1,
            "total_users_imported": 450,
            "success_rate": 94.5,
            "recent_jobs": [...]
        },
        "invitation_campaigns": {
            "total": 5,
            "active": 1,
            "completed": 4,
            "total_sent": 200,
            "total_accepted": 175,
            "acceptance_rate": 87.5,
            "expiring_soon": 3,
            "recent_campaigns": [...]
        }
    }
    """
    try:
        # Determine hospital context
        if request.user.role == 'super_admin':
            # Super admin sees all hospitals
            hospital_filter = None
            hospitals = Hospital.objects.all()
        elif request.user.role == 'hospital_admin':
            # Hospital admin sees only their hospital
            hospital_filter = get_request_hospital(request)
            hospitals = [hospital_filter] if hospital_filter else []
        else:
            return Response(
                {'error': 'Only hospital admins and super admins can access batch operations summary'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Build import jobs summary
        import_jobs_query = BatchImportJob.objects.all()
        if hospital_filter:
            import_jobs_query = import_jobs_query.filter(hospital=hospital_filter)
        
        import_jobs_stats = {
            'total': import_jobs_query.count(),
            'active': import_jobs_query.filter(status__in=['validating', 'processing']).count(),
            'completed': import_jobs_query.filter(status='completed').count(),
            'failed': import_jobs_query.filter(status='failed').count(),
        }
        
        # Calculate total users imported and success rate
        total_imported_records = import_jobs_query.aggregate(
            total=Sum('success_count')
        )['total'] or 0
        total_processed = import_jobs_query.aggregate(
            total=Sum('processed_count')
        )['total'] or 0
        
        import_jobs_stats['total_users_imported'] = total_imported_records
        if total_processed > 0:
            import_jobs_stats['success_rate'] = round((total_imported_records / total_processed) * 100, 1)
        else:
            import_jobs_stats['success_rate'] = 0
        
        # Recent import jobs (last 5)
        recent_import_jobs = []
        for job in import_jobs_query.order_by('-created_at')[:5]:
            recent_import_jobs.append({
                'id': str(job.id),
                'filename': job.filename,
                'status': job.status,
                'progress': job.progress_percent,
                'total_records': job.total_records,
                'success_count': job.success_count,
                'created_at': job.created_at.isoformat(),
                'hospital': job.hospital.name if job.hospital else 'Unknown'
            })
        
        import_jobs_stats['recent_jobs'] = recent_import_jobs
        
        # Build invitation campaigns summary
        invitation_campaigns_query = BulkInvitationJob.objects.all()
        if hospital_filter:
            invitation_campaigns_query = invitation_campaigns_query.filter(hospital=hospital_filter)
        
        campaign_stats = {
            'total': invitation_campaigns_query.count(),
            'active': invitation_campaigns_query.filter(status__in=['sending', 'sent', 'partial']).count(),
            'completed': invitation_campaigns_query.filter(status='completed').count(),
        }
        
        # Calculate invitation metrics
        total_sent = invitation_campaigns_query.aggregate(
            total=Sum('sent_count')
        )['total'] or 0
        total_accepted = invitation_campaigns_query.aggregate(
            total=Sum('accepted_count')
        )['total'] or 0
        
        campaign_stats['total_sent'] = total_sent
        campaign_stats['total_accepted'] = total_accepted
        if total_sent > 0:
            campaign_stats['acceptance_rate'] = round((total_accepted / total_sent) * 100, 1)
        else:
            campaign_stats['acceptance_rate'] = 0
        
        # Count expiring soon (next 24 hours)
        now = timezone.now()
        expiring_soon_items = BulkInvitationItem.objects.filter(
            status='sent',
            expires_at__lte=now + timedelta(hours=24),
            expires_at__gt=now
        )
        campaign_stats['expiring_soon'] = expiring_soon_items.count()
        
        # Recent campaigns (last 5)
        recent_campaigns = []
        for campaign in invitation_campaigns_query.order_by('-created_at')[:5]:
            recent_campaigns.append({
                'id': str(campaign.id),
                'campaign_name': campaign.campaign_name,
                'status': campaign.status,
                'progress': campaign.progress_percent,
                'total_invitations': campaign.total_invitations,
                'sent_count': campaign.sent_count,
                'accepted_count': campaign.accepted_count,
                'created_at': campaign.created_at.isoformat(),
                'hospital': campaign.hospital.name if campaign.hospital else 'Unknown'
            })
        
        campaign_stats['recent_campaigns'] = recent_campaigns
        
        # Log the action
        if hospital_filter:
            AuditLog.log_action(
                user=request.user,
                action='VIEW',
                resource_type='BatchOperationsSummary',
                resource_id='summary',
                hospital=hospital_filter,
                details={'type': 'dashboard_summary'}
            )
        
        return Response({
            'import_jobs': import_jobs_stats,
            'invitation_campaigns': campaign_stats,
            'timestamp': timezone.now().isoformat()
        })
    
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching batch operations summary: {str(e)}")
        return Response(
            {'error': 'Failed to fetch batch operations summary'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_import_create(request):
    """
    Start a new batch import job.

    Expects: {
        "filename": "users.csv",
        "items": [
            {"email": "...", "full_name": "...", "role": "nurse", ...},
            ...
        ]
    }
    """
    try:
        # Only hospital admins can create batch imports
        if request.user.role not in ['hospital_admin', 'super_admin']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        hospital = get_request_hospital(request)
        if not hospital:
            return Response({'error': 'No hospital context'}, status=status.HTTP_400_BAD_REQUEST)

        filename = request.data.get('filename', 'import.csv')
        items = request.data.get('items', [])

        if not items:
            return Response({'error': 'No items provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Create batch job
        job = BatchImportJob.objects.create(
            hospital=hospital,
            created_by=request.user,
            filename=filename,
            total_records=len(items),
            status='validating'
        )

        # Create import items
        validation_errors = {}

        for idx, item in enumerate(items, 1):
            errors = []

            # Validate required fields
            email = item.get('email', '').strip()
            full_name = item.get('full_name', '').strip()
            role = item.get('role', '').strip()

            if not email or '@' not in email:
                errors.append('Invalid email format')
            if not full_name or len(full_name) < 2:
                errors.append('Full name required (min 2 chars)')
            if role not in ['doctor', 'nurse', 'lab_technician', 'receptionist', 'hospital_admin', 'super_admin']:
                errors.append(f'Invalid role: {role}')

            # Check for duplicate email
            if User.objects.filter(email=email).exists():
                errors.append('Email already exists')

            # Check for duplicate in batch
            if BatchImportItem.objects.filter(batch_job=job, email=email).exists():
                errors.append('Duplicate email in batch')

            ward_id = item.get('ward_id')
            if ward_id and role == 'nurse':
                try:
                    Ward.objects.get(id=ward_id, hospital=hospital)
                except Ward.DoesNotExist:
                    errors.append(f'Ward not found: {ward_id}')

            # Create item
            BatchImportItem.objects.create(
                batch_job=job,
                row_number=idx,
                email=email,
                full_name=full_name,
                phone=item.get('phone', ''),
                role=role,
                ward_id=ward_id if ward_id and role == 'nurse' else None,
                status='validation_error' if errors else 'validated',
                validation_errors=errors
            )

            if errors:
                validation_errors[f'row_{idx}'] = errors
                job.validation_error_count += 1
            else:
                job.success_count += 1

        job.validation_summary = validation_errors
        job.status = 'validated' if job.validation_error_count == 0 else 'failed'
        job.save()

        AuditLog.log_action(
            user=request.user,
            action='CREATE',
            resource_type='BatchImportJob',
            resource_id=sanitize_audit_resource_id(str(job.id)),
            hospital=hospital,
            details={'filename': filename, 'total_records': len(items), 'errors': len(validation_errors)}
        )

        return Response({
            'job_id': str(job.id),
            'filename': job.filename,
            'total_records': job.total_records,
            'valid_records': job.total_records - job.validation_error_count,
            'validation_errors': job.validation_error_count,
            'status': job.status,
            'validation_summary': job.validation_summary
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_import_detail(request, job_id):
    """Get batch import job details and progress."""
    try:
        hospital = get_request_hospital(request)
        job = BatchImportJob.objects.get(id=job_id, hospital=hospital)

        return Response({
            'id': str(job.id),
            'filename': job.filename,
            'status': job.status,
            'total_records': job.total_records,
            'processed_count': job.processed_count,
            'success_count': job.success_count,
            'validation_error_count': job.validation_error_count,
            'processing_error_count': job.processing_error_count,
            'progress_percent': job.progress_percent,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'validation_summary': job.validation_summary,
        })

    except BatchImportJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_import_items_list(request, job_id):
    """Get import items with filtering and pagination."""
    try:
        hospital = get_request_hospital(request)
        job = BatchImportJob.objects.get(id=job_id, hospital=hospital)

        # Filter options
        status_filter = request.data.get('status')
        page = request.data.get('page', 1)
        per_page = request.data.get('per_page', 50)

        items_query = BatchImportItem.objects.filter(batch_job=job)

        if status_filter:
            items_query = items_query.filter(status=status_filter)

        # Pagination
        total = items_query.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = items_query[start:end]

        items_data = []
        for item in items:
            items_data.append({
                'id': str(item.id),
                'row_number': item.row_number,
                'email': item.email,
                'full_name': item.full_name,
                'role': item.role,
                'status': item.status,
                'validation_errors': item.validation_errors,
                'processing_error': item.processing_error,
                'processed_at': item.processed_at.isoformat() if item.processed_at else None
            })

        return Response({
            'items': items_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        })

    except BatchImportJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_import_export(request, job_id):
    """Export batch import results as CSV."""
    try:
        hospital = get_request_hospital(request)
        job = BatchImportJob.objects.get(id=job_id, hospital=hospital)

        # Build CSV
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['Row', 'Email', 'Name', 'Role', 'Status', 'Errors'])

        # Items
        items = BatchImportItem.objects.filter(batch_job=job)
        for item in items:
            errors = '; '.join(item.validation_errors + ([item.processing_error] if item.processing_error else []))
            writer.writerow([
                item.row_number,
                item.email,
                item.full_name,
                item.role,
                item.status,
                errors
            ])

        return Response({
            'csv': output.getvalue(),
            'filename': f"batch-import-{job_id}.csv"
        })

    except BatchImportJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_invitation_create(request):
    """
    Create a bulk invitation campaign.

    Expects: {
        "campaign_name": "Q1 Onboarding",
        "invitations": [
            {"email": "...", "full_name": "...", "role": "doctor"},
            ...
        ],
        "expiry_days": 7
    }
    """
    try:
        if request.user.role not in ['hospital_admin', 'super_admin']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        hospital = get_request_hospital(request)
        if not hospital:
            return Response({'error': 'No hospital context'}, status=status.HTTP_400_BAD_REQUEST)

        campaign_name = request.data.get('campaign_name')
        invitations = request.data.get('invitations', [])
        expiry_days = request.data.get('expiry_days', 7)

        if not campaign_name or not invitations:
            return Response({'error': 'Missing campaign_name or invitations'}, status=status.HTTP_400_BAD_REQUEST)

        # Create campaign
        campaign = BulkInvitationJob.objects.create(
            hospital=hospital,
            created_by=request.user,
            campaign_name=campaign_name,
            total_invitations=len(invitations),
            invitation_expiry_days=expiry_days
        )

        # Create invitation items
        for inv in invitations:
            email = inv.get('email', '').strip()
            full_name = inv.get('full_name', '').strip()
            role = inv.get('role', '').strip()

            # Check if user already exists
            if not User.objects.filter(email=email).exists():
                BulkInvitationItem.objects.create(
                    campaign=campaign,
                    email=email,
                    full_name=full_name,
                    role=role,
                    status='pending'
                )

        AuditLog.log_action(
            user=request.user,
            action='CREATE',
            resource_type='BulkInvitationJob',
            resource_id=sanitize_audit_resource_id(str(campaign.id)),
            hospital=hospital,
            details={'campaign_name': campaign_name, 'total_invitations': len(invitations)}
        )

        return Response({
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.campaign_name,
            'total_invitations': campaign.total_invitations,
            'status': campaign.status
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bulk_invitation_detail(request, campaign_id):
    """Get bulk invitation campaign details."""
    try:
        hospital = get_request_hospital(request)
        campaign = BulkInvitationJob.objects.get(id=campaign_id, hospital=hospital)

        return Response({
            'id': str(campaign.id),
            'campaign_name': campaign.campaign_name,
            'status': campaign.status,
            'total_invitations': campaign.total_invitations,
            'sent_count': campaign.sent_count,
            'failed_count': campaign.failed_count,
            'accepted_count': campaign.accepted_count,
            'expired_count': campaign.expired_count,
            'pending_count': campaign.pending_count,
            'progress_percent': campaign.progress_percent,
            'expiry_days': campaign.invitation_expiry_days,
            'created_at': campaign.created_at.isoformat(),
            'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
        })

    except BulkInvitationJob.DoesNotExist:
        return Response({'error': 'Campaign not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bulk_invitation_expiration_check(request):
    """Check for expiring invitations across all hospitals."""
    try:
        if request.user.role != 'super_admin':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        # Find invitations expiring in next 24 hours
        now = timezone.now()
        expiring_soon = BulkInvitationItem.objects.filter(
            status='sent',
            expires_at__lte=now + timedelta(hours=24),
            expires_at__gt=now
        )

        # Find expired invitations
        expired = BulkInvitationItem.objects.filter(
            status='sent',
            expires_at__lte=now
        )

        # Update expired status
        expired.update(status='expired')

        expiring_data = []
        for item in expiring_soon:
            expiring_data.append({
                'id': str(item.id),
                'email': item.email,
                'campaign_id': str(item.campaign.id),
                'campaign_name': item.campaign.campaign_name,
                'expires_at': item.expires_at.isoformat(),
                'hours_remaining': round((item.expires_at - now).total_seconds() / 3600)
            })

        return Response({
            'expiring_soon': expiring_data,
            'expired_count': expired.count()
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_invitation_send_reminders(request):
    """
    Send reminder emails to invitations expiring in next 24 hours.

    Only accessible to super_admin.
    """
    try:
        if request.user.role != 'super_admin':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()

        # Find invitations expiring in next 24 hours that haven't been reminded
        expiring_soon = BulkInvitationItem.objects.filter(
            status='sent',
            expires_at__lte=now + timedelta(hours=24),
            expires_at__gt=now
        )

        reminders_sent = 0
        errors = []

        for item in expiring_soon:
            try:
                # In a real system, this would send an email via a mail service
                # For now, we just log that a reminder was triggered
                AuditLog.log_action(
                    user=request.user,
                    action='SEND_REMINDER',
                    resource_type='BulkInvitationItem',
                    resource_id=sanitize_audit_resource_id(str(item.id)),
                    hospital=item.campaign.hospital,
                    details={
                        'email': item.email,
                        'campaign': item.campaign.campaign_name,
                        'expires_at': item.expires_at.isoformat(),
                        'hours_remaining': round((item.expires_at - now).total_seconds() / 3600)
                    }
                )
                reminders_sent += 1
            except Exception as e:
                errors.append(f"Failed to send reminder to {item.email}: {str(e)}")

        return Response({
            'reminders_sent': reminders_sent,
            'errors': errors,
            'total_expiring': expiring_soon.count()
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bulk_invitation_reminder_schedule(request):
    """
    Get reminder schedule configuration.

    Shows when reminders are sent relative to expiration time.
    """
    try:
        schedule = {
            'reminders': [
                {
                    'name': 'First reminder',
                    'days_before_expiry': 3,
                    'description': 'Sent 3 days before expiration'
                },
                {
                    'name': 'Final reminder',
                    'hours_before_expiry': 24,
                    'description': 'Sent 24 hours before expiration'
                }
            ],
            'next_check': (timezone.now() + timedelta(hours=1)).isoformat(),
            'last_check': timezone.now().isoformat()
        }

        return Response(schedule)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
