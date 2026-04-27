"""
Batch Operations Models.

Handles bulk user imports, bulk invitations, and batch operation tracking.

Models:
- BatchImportJob: Top-level batch import tracking
- BatchImportItem: Individual user records in a batch
- BulkInvitationJob: Bulk invitation campaign tracking
- BulkInvitationItem: Individual invitations in a campaign
"""

import uuid
from django.db import models
from django.utils import timezone
from core.models import Hospital, User


class BatchImportJob(models.Model):
    """
    Top-level tracking for bulk user import operations.

    Tracks progress, validation results, and completion status.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('paused', 'Paused'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='batch_import_jobs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name='batch_import_jobs_created')

    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Counts
    total_records = models.IntegerField(default=0)
    processed_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    validation_error_count = models.IntegerField(default=0)
    processing_error_count = models.IntegerField(default=0)

    # Error tracking
    validation_summary = models.JSONField(default=dict, blank=True, help_text="Summary of validation errors")
    processing_errors = models.JSONField(default=list, blank=True, help_text="List of processing errors")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'batch_import_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Batch {self.filename} ({self.status})"

    @property
    def progress_percent(self):
        """Calculate progress percentage."""
        if self.total_records == 0:
            return 0
        return round((self.processed_count / self.total_records) * 100)

    @property
    def error_count(self):
        """Total errors across validation and processing."""
        return self.validation_error_count + self.processing_error_count


class BatchImportItem(models.Model):
    """
    Individual user record in a batch import.

    Tracks validation and processing status for each row.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validated', 'Validated'),
        ('processing', 'Processing'),
        ('created', 'Created'),
        ('validation_error', 'Validation Error'),
        ('processing_error', 'Processing Error'),
        ('skipped', 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_job = models.ForeignKey(BatchImportJob, on_delete=models.CASCADE, related_name='items')

    row_number = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # User data
    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=50)  # doctor, nurse, lab_technician, etc.
    ward_id = models.UUIDField(null=True, blank=True)

    # Validation results
    validation_errors = models.JSONField(default=list, blank=True)

    # Processing results
    created_user_id = models.UUIDField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'batch_import_item'
        ordering = ['row_number']
        indexes = [
            models.Index(fields=['batch_job', 'status']),
        ]
        unique_together = ('batch_job', 'row_number')

    def __str__(self):
        return f"Row {self.row_number}: {self.email}"


class BulkInvitationJob(models.Model):
    """
    Top-level tracking for bulk invitation campaigns.

    Tracks invitation batches, delivery status, and expiration.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('partial', 'Partially Sent'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='bulk_invitation_jobs')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulk_invitation_jobs_created')

    campaign_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Counts
    total_invitations = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    accepted_count = models.IntegerField(default=0)
    expired_count = models.IntegerField(default=0)

    # Configuration
    invitation_expiry_days = models.IntegerField(default=7)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bulk_invitation_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Campaign: {self.campaign_name}"

    @property
    def progress_percent(self):
        """Calculate invitation progress percentage."""
        if self.total_invitations == 0:
            return 0
        return round(((self.sent_count + self.failed_count) / self.total_invitations) * 100)

    @property
    def pending_count(self):
        """Invitations not yet sent."""
        return self.total_invitations - self.sent_count - self.failed_count


class BulkInvitationItem(models.Model):
    """
    Individual invitation in a bulk campaign.

    Tracks delivery, acceptance, and expiration status.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(BulkInvitationJob, on_delete=models.CASCADE, related_name='invitations')

    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=50)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Invitation tracking
    invitation_token = models.CharField(max_length=255, unique=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Acceptance tracking
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by_user_id = models.UUIDField(null=True, blank=True)

    # Delivery error
    delivery_error = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bulk_invitation_item'
        ordering = ['email']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = ('campaign', 'email')

    def __str__(self):
        return f"{self.email} - {self.status}"

    @property
    def is_expired(self):
        """Check if invitation has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
