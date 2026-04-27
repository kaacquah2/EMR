"""
AIDeploymentLog Model for Clinical AI Feature Deployment and Approval.

This model tracks hospital-by-hospital approval of clinical AI features.
When a hospital admin enables clinical AI, this model records validation
metrics, approval notes, and audit trail.

The circuit breaker in api/ai/governance.py queries this to check if
clinical AI is allowed for a hospital.
"""

from uuid import uuid4
from django.db import models
from django.utils import timezone

from core.models import Hospital, User


class AIDeploymentLog(models.Model):
    """
    Tracks AI clinical feature deployment and approval per hospital.

    When a hospital admin enables clinical AI features for their facility,
    this model records:
    - Which hospital approved it
    - When it was approved
    - By which hospital admin user
    - What model version was validated
    - Performance metrics (AUC-ROC, sensitivity, specificity)
    - Approval notes

    The circuit breaker (check_ai_clinical_features_enabled in governance.py)
    queries this model to determine if clinical AI is allowed.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='ai_deployments')
    enabled_by = models.ForeignKey(User, on_delete=models.PROTECT, help_text="Hospital admin who approved")

    # Deployment status
    enabled = models.BooleanField(default=False, help_text="Is clinical AI currently enabled for this hospital?")
    enabled_at = models.DateTimeField(auto_now_add=True, db_index=True)
    disabled_at = models.DateTimeField(null=True, blank=True, help_text="When AI was disabled (if applicable)")

    # Model tracking
    model_version = models.CharField(
        max_length=50,
        default='1.0.0-placeholder',
        help_text="Version of model being deployed (e.g., 1.0.0-mimic-iv or 1.1.0-ghana-data)"
    )

    # Validation metrics (stored as JSON)
    # Expected structure:
    # {
    #     "overall_auc_roc": 0.85,
    #     "overall_sensitivity": 0.78,
    #     "overall_specificity": 0.88,
    #     "diseases": {
    #         "malaria": {"auc_roc": 0.92, "sensitivity": 0.85, "specificity": 0.95},
    #         "hypertension": {"auc_roc": 0.78, "sensitivity": 0.70, "specificity": 0.85},
    #         ...
    #     },
    #     "test_data_size": 1000,
    #     "test_data_source": "MIMIC-IV",
    #     "training_date": "2026-04-20"
    # }
    validation_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Model performance metrics: AUC-ROC, sensitivity, specificity per disease"
    )

    # Admin notes
    approval_notes = models.TextField(
        blank=True,
        help_text="Hospital admin notes on approval (why approved, any caveats, etc.)"
    )

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-enabled_at']
        indexes = [
            models.Index(fields=['hospital', 'enabled', '-enabled_at']),
        ]
        verbose_name = "AI Deployment Log"
        verbose_name_plural = "AI Deployment Logs"

    def __str__(self):
        status = "ENABLED" if self.enabled else "DISABLED"
        return f"{self.hospital.name} - AI {status} ({self.model_version}) - {self.enabled_at.strftime('%Y-%m-%d')}"

    @classmethod
    def get_latest_for_hospital(cls, hospital: Hospital):
        """Get the most recent deployment log for a hospital."""
        return cls.objects.filter(hospital=hospital).first()

    @classmethod
    def is_clinical_ai_enabled_for_hospital(cls, hospital: Hospital) -> bool:
        """Check if clinical AI is currently enabled for this hospital."""
        if not hospital:
            return False
        latest = cls.get_latest_for_hospital(hospital)
        return latest.enabled if latest else False

    def validate_metrics(self) -> tuple[bool, str]:
        """
        Validate that deployment metrics meet clinical thresholds.

        Returns:
            (is_valid, message) - True if metrics acceptable, False + reason if not
        """
        if not self.validation_metrics:
            return False, "No validation metrics provided"

        metrics = self.validation_metrics
        min_auc_roc = 0.80
        min_sensitivity = 0.75
        min_specificity = 0.85

        # Check overall metrics
        auc_roc = metrics.get('overall_auc_roc', 0)
        sensitivity = metrics.get('overall_sensitivity', 0)
        specificity = metrics.get('overall_specificity', 0)

        if auc_roc < min_auc_roc:
            return False, f"AUC-ROC {auc_roc:.2f} below minimum {min_auc_roc}"
        if sensitivity < min_sensitivity:
            return False, f"Sensitivity {sensitivity:.2f} below minimum {min_sensitivity}"
        if specificity < min_specificity:
            return False, f"Specificity {specificity:.2f} below minimum {min_specificity}"

        return True, "All metrics meet clinical thresholds"


class ModelMetrics(models.Model):
    """
    Tracks performance metrics for trained AI models.
    
    Stores validation metrics (AUC-ROC, sensitivity, specificity, precision, F1)
    for model versions. Used to validate models before clinical deployment.
    
    Clinical deployment thresholds:
    - AUC-ROC >= 0.80 (Area Under Receiver Operating Characteristic Curve)
    - Sensitivity >= 0.75 (True Positive Rate)
    - Specificity >= 0.85 (True Negative Rate)
    """
    
    DATASET_SOURCES = [
        ('mimic', 'MIMIC-IV (Medical Information Mart for Intensive Care)'),
        ('synthetic', 'Synthetic Ghana Data'),
        ('ghana', 'Real Ghana Health Service Data'),
        ('hybrid', 'Hybrid (Multiple Sources)'),
        ('kaggle', 'Kaggle Public Datasets'),
        ('uci', 'UCI Machine Learning Repository'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    model_version = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Model version identifier (e.g., 1.0.0-hybrid, 1.1.0-mimic-iv)"
    )
    
    # Performance metrics (must meet clinical thresholds)
    auc_roc = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        help_text="Area Under ROC Curve (0-1). Clinical min: 0.80"
    )
    sensitivity = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        help_text="True Positive Rate (0-1). Clinical min: 0.75"
    )
    specificity = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        help_text="True Negative Rate (0-1). Clinical min: 0.85"
    )
    precision = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Precision (0-1)"
    )
    f1_score = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="F1 Score (0-1)"
    )
    
    # Dataset and validation info
    validation_date = models.DateTimeField(auto_now_add=True, db_index=True)
    dataset_size = models.IntegerField(help_text="Number of samples used in validation")
    dataset_source = models.CharField(
        max_length=20,
        choices=DATASET_SOURCES,
        default='hybrid',
        help_text="Source of validation dataset"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes on model validation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'model_metrics'
        ordering = ['-validation_date']
        indexes = [
            models.Index(fields=['model_version']),
            models.Index(fields=['-validation_date']),
        ]
    
    def __str__(self):
        return f"{self.model_version} (AUC: {self.auc_roc:.2f})"
    
    def meets_clinical_thresholds(self) -> tuple[bool, list[str]]:
        """
        Check if model meets all clinical deployment thresholds.
        
        Returns:
            (is_valid, errors) - True if all thresholds met, list of errors if not
        """
        errors = []
        
        if float(self.auc_roc) < 0.80:
            errors.append(f"AUC-ROC {self.auc_roc:.4f} below minimum 0.80")
        if float(self.sensitivity) < 0.75:
            errors.append(f"Sensitivity {self.sensitivity:.4f} below minimum 0.75")
        if float(self.specificity) < 0.85:
            errors.append(f"Specificity {self.specificity:.4f} below minimum 0.85")
        
        return len(errors) == 0, errors


class AIDeploymentApproval(models.Model):
    """
    Hospital-level approval for AI model deployment.
    
    Records when a hospital admin approves (or revokes) an AI model for clinical use.
    Includes confidence threshold configuration per hospital and full approval workflow.
    
    Audit trail:
    - All approvals/revocations logged to AuditLog with action='AI_APPROVAL_GRANT'/'AI_APPROVAL_REVOKE'
    - Metadata stores config flags and approval context
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name='ai_approvals',
        help_text="Hospital approving this model"
    )
    model_version = models.CharField(
        max_length=50,
        help_text="Model version being approved (e.g., 1.0.0-hybrid)"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_approvals_given',
        help_text="Hospital admin who approved"
    )
    
    # Approval tracking
    approved_at = models.DateTimeField(auto_now_add=True, db_index=True)
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When approval was revoked (if applicable)"
    )
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_approvals_revoked',
        help_text="Admin who revoked approval"
    )
    
    # Configuration
    confidence_threshold = models.DecimalField(
        max_digits=4,
        decimal_places=4,
        default='0.80',
        help_text="Minimum confidence threshold for this hospital (0.75-1.0)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Is this approval currently active?"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Config flags and approval context"
    )
    notes = models.TextField(
        blank=True,
        help_text="Approval notes (why approved, caveats, etc.)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_deployment_approval'
        unique_together = ('hospital', 'model_version')
        ordering = ['-approved_at']
        indexes = [
            models.Index(fields=['hospital', 'enabled', '-approved_at']),
            models.Index(fields=['model_version', '-approved_at']),
        ]
    
    def __str__(self):
        status = "ACTIVE" if self.enabled else "REVOKED"
        return f"{self.hospital.name} - {self.model_version} ({status})"
    
    def is_active(self) -> bool:
        """Check if approval is currently active (not revoked)."""
        return self.enabled and self.revoked_at is None

