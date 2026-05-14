import uuid
from django.db import models
from core.models import User

class ModelVersion(models.Model):
    """
    Tracks versions, evaluation metrics, and approval status of AI models.
    """
    MODEL_TYPES = [
        ('risk_prediction', 'Risk Prediction'),
        ('triage', 'Triage'),
        ('diagnosis', 'Diagnosis'),
        ('similarity', 'Similarity Search'),
    ]

    DATA_SOURCES = [
        ('synthetic', 'Synthetic Data'),
        ('anonymized_local', 'Anonymized Local Data'),
        ('anonymized_federated', 'Anonymized Federated Data'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_type = models.CharField(max_length=50, choices=MODEL_TYPES)
    version_tag = models.CharField(max_length=100, help_text="e.g. v2.1.0-20260501")
    trained_at = models.DateTimeField(auto_now_add=True)
    trained_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trained_models')
    
    training_data_source = models.CharField(max_length=50, choices=DATA_SOURCES, default='synthetic')
    training_sample_count = models.IntegerField(default=0)
    
    # Stores classification metrics: accuracy, precision, recall, f1, auc_roc, etc.
    evaluation_metrics = models.JSONField(default=dict)
    
    # Stores delta vs the previous production model
    comparison_vs_previous = models.JSONField(default=dict, null=True, blank=True)
    
    is_production = models.BooleanField(default=False, help_text="Is this the currently active model in production?")
    clinical_use_approved = models.BooleanField(default=False, help_text="Has this version been clinically validated?")
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_models')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True, null=True, help_text="Clinical validation summary")
    
    joblib_path = models.CharField(max_length=500, help_text="Absolute path to the saved .joblib file")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-trained_at']
        indexes = [
            models.Index(fields=['model_type', 'is_production']),
            models.Index(fields=['version_tag']),
        ]

    def __str__(self):
        return f"{self.model_type} {self.version_tag} ({'PROD' if self.is_production else 'DRAFT'})"
