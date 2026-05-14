"""
AI Analysis Storage Models.

Persists AI analysis results for audit, feedback, and performance tracking.

Models:
- AIAnalysis: Top-level analysis record
- DiseaseRiskPrediction: Individual disease risk scores
- DiagnosisSuggestion: Suggested diagnoses with confidence
- TriageAssessment: Emergency severity classification
- PatientSimilarityMatch: Similar patient case references
- ReferralRecommendation: Recommended hospitals
"""

import logging
from uuid import uuid4

from django.db import models
from django.utils import timezone

from core.models import Hospital, User
from patients.models import Patient
from records.models import Encounter, Prescription, Diagnosis

logger = logging.getLogger(__name__)


def _default_list():
    """Helper for JSONField default empty list."""
    return []


def _default_dict():
    """Helper for JSONField default empty dict."""
    return {}


class AIAnalysis(models.Model):
    """
    Top-level AI analysis record linking all outputs.

    Stores the complete analysis result for auditing and historical tracking.
    """

    ANALYSIS_TYPES = [
        ('comprehensive', 'Comprehensive Multi-Agent Analysis'),
        ('risk_prediction', 'Disease Risk Prediction'),
        ('clinical_decision_support', 'Clinical Decision Support'),
        ('triage', 'Patient Triage'),
        ('similarity_search', 'Similar Patient Search'),
        ('referral', 'Hospital Referral Recommendation'),
        # NEW TYPES
        ('differentials', 'Differential Diagnosis'),
        ('encounter_summary', 'Encounter Summary'),
        ('discharge_summary', 'Discharge Summary'),
        ('readmission_risk', 'Readmission Risk'),
        ('icd10_suggest', 'ICD-10 Suggestion'),
        ('ward_forecast', 'Ward Bed Forecast'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ai_analyses')
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='ai_analyses')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    analysis_type = models.CharField(max_length=50, choices=ANALYSIS_TYPES, default='comprehensive')

    # Analysis metadata
    overall_confidence = models.FloatField(default=0.0, help_text="0-1 confidence score")
    agents_executed = models.JSONField(default=_default_list, blank=True, help_text="Names of AI agents that executed")

    # Results summary
    clinical_summary = models.TextField(blank=True)
    recommended_actions = models.JSONField(default=_default_list, help_text="List of recommended clinical actions")
    alerts = models.JSONField(default=_default_list, help_text="Clinical alerts generated")
    
    # Normalized fields for analytics
    alerts_count = models.IntegerField(default=0)
    has_critical_alerts = models.BooleanField(default=False)
    is_at_risk = models.BooleanField(default=False, db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Analysis request context
    chief_complaint = models.TextField(blank=True)
    additional_context = models.JSONField(default=_default_dict, blank=True)

    class Meta:
        db_table = 'ai_analysis'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['analysis_type', '-created_at']),
            models.Index(fields=['is_at_risk', '-created_at']),
            models.Index(fields=['has_critical_alerts']),
        ]

    def __str__(self):
        return f"{self.analysis_type} for {self.patient.ghana_health_id} ({self.created_at.date()})"


class DiseaseRiskPrediction(models.Model):
    """
    Disease risk prediction results linked to an analysis.

    Stores individual disease risk scores, confidence, and contributing factors.
    """

    DISEASES = [
        ('heart_disease', 'Heart Disease'),
        ('diabetes', 'Diabetes Mellitus'),
        ('stroke', 'Stroke (CVA)'),
        ('pneumonia', 'Pneumonia'),
        ('hypertension', 'Hypertension'),
        ('kidney_disease', 'Kidney Disease'),
        ('copd', 'COPD'),
        ('asthma', 'Asthma'),
        ('cancer', 'Cancer'),
    ]

    RISK_CATEGORIES = [
        ('low', 'Low Risk (0-20%)'),
        ('medium', 'Medium Risk (20-50%)'),
        ('high', 'High Risk (50-80%)'),
        ('critical', 'Critical Risk (80%+)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name='disease_predictions'
    )

    disease = models.CharField(max_length=50, choices=DISEASES)
    risk_score = models.FloatField(help_text="0-100 scale")
    risk_category = models.CharField(max_length=20, choices=RISK_CATEGORIES)
    confidence = models.FloatField(help_text="0-1 confidence")

    # Contributing factors
    contributing_factors = models.JSONField(
        default=_default_list,
        blank=True,
        help_text="List of factors that contributed to this prediction"
    )

    # Clinical recommendations
    recommendations = models.JSONField(
        default=_default_list,
        blank=True,
        help_text="Clinical recommendations for this disease",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'disease_risk_prediction'
        unique_together = ('analysis', 'disease')
        ordering = ['-risk_score']
        indexes = [
            models.Index(fields=['analysis', '-risk_score']),
            models.Index(fields=['disease', '-risk_score']),
            models.Index(fields=['risk_category']),
        ]

    def __str__(self):
        return f"{self.disease} - {self.risk_category} ({self.risk_score:.0f}%)"


class DiagnosisSuggestion(models.Model):
    """
    Differential diagnosis suggestions from CDS engine.

    Stores suggested diagnoses ranked by probability.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name='diagnosis_suggestions'
    )

    rank = models.IntegerField(help_text="Ranking among suggestions (1=most likely)")
    diagnosis = models.CharField(max_length=200)
    icd10_code = models.CharField(max_length=10, blank=True)
    probability = models.FloatField(help_text="0-1 likelihood")
    confidence = models.FloatField(help_text="0-1 model confidence")

    # Supporting evidence
    matching_symptoms = models.JSONField(blank=True, default=_default_list)
    recommended_tests = models.JSONField(blank=True, default=_default_list)
    clinical_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'diagnosis_suggestion'
        ordering = ['analysis', 'rank']
        indexes = [
            models.Index(fields=['analysis', 'rank']),
        ]

    def __str__(self):
        return f"#{self.rank}: {self.diagnosis} ({self.probability:.0%})"


class TriageAssessment(models.Model):
    """
    Emergency severity triage classification.

    Stores triage level, ESI score, and urgency indicators.
    """

    TRIAGE_LEVELS = [
        ('critical', 'Critical (Immediate)'),
        ('high', 'High (Urgent)'),
        ('medium', 'Medium (Soon)'),
        ('low', 'Low (Routine)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    analysis = models.OneToOneField(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name='triage_assessment'
    )

    triage_level = models.CharField(max_length=20, choices=TRIAGE_LEVELS)
    triage_score = models.FloatField(help_text="0-100 scale")
    confidence = models.FloatField(help_text="0-1 confidence")
    esi_level = models.IntegerField(help_text="Emergency Severity Index (1-5)")

    # Assessment details
    reason = models.TextField()
    indicators = models.JSONField(
        default=_default_list,
        blank=True,
        help_text="List of indicators that determined triage level"
    )
    recommended_action = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'triage_assessment'
        ordering = ['analysis', '-triage_score']

    def __str__(self):
        return f"ESI Level {self.esi_level}: {self.triage_level.upper()}"


class PatientSimilarityMatch(models.Model):
    """
    Similar patient case references for treatment benchmarking.

    Links current patient to similar cases.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name='similar_patients'
    )

    similar_patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='similarity_matches'
    )

    rank = models.IntegerField(help_text="Ranking by similarity (1=most similar)")
    similarity_score = models.FloatField(help_text="0-1 similarity")

    # Comparison metadata
    matching_conditions = models.JSONField(blank=True, default=_default_list)
    treatment_outcome = models.CharField(max_length=200, blank=True)
    outcome_success_rate = models.FloatField(null=True, blank=True, help_text="0-1 success rate")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_similarity_match'
        unique_together = ('analysis', 'similar_patient')
        ordering = ['analysis', 'rank']
        indexes = [
            models.Index(fields=['analysis', 'rank']),
            models.Index(fields=['similar_patient']),
        ]

    def __str__(self):
        return f"Similar patient #{self.rank} (similarity: {self.similarity_score:.0%})"


class ReferralRecommendation(models.Model):
    """
    Recommended hospitals for inter-hospital referral.

    Scores hospitals based on specialty, capacity, and distance.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    analysis = models.ForeignKey(
        AIAnalysis,
        on_delete=models.CASCADE,
        related_name='referral_recommendations'
    )

    recommended_hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name='referral_recommendations'
    )

    rank = models.IntegerField(help_text="Ranking by suitability (1=best match)")
    specialty_match = models.FloatField(help_text="0-1 specialty match score")

    # Hospital status
    bed_availability = models.IntegerField(null=True, blank=True)
    distance_km = models.FloatField(null=True, blank=True)
    success_rate = models.FloatField(null=True, blank=True, help_text="0-1 treatment success rate")

    reason = models.TextField(help_text="Why this hospital is recommended")

    # Referral action tracking
    referral_created = models.BooleanField(default=False)
    referral_accepted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'referral_recommendation'
        unique_together = ('analysis', 'recommended_hospital')
        ordering = ['analysis', 'rank']
        indexes = [
            models.Index(fields=['analysis', 'rank']),
            models.Index(fields=['recommended_hospital']),
        ]

    def __str__(self):
        return f"#{self.rank}: {self.recommended_hospital.name} (specialty match: {self.specialty_match:.0%})"


class AIAnalysisCounter(models.Model):
    """
    Track AI analysis usage statistics per hospital per day.

    Used for quotas, monitoring, and cost tracking.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='ai_analysis_counters')
    date = models.DateField(db_index=True)

    # Analysis counts
    total_analyses = models.IntegerField(default=0)
    risk_predictions = models.IntegerField(default=0)
    cds_queries = models.IntegerField(default=0)
    triage_assessments = models.IntegerField(default=0)
    similarity_searches = models.IntegerField(default=0)
    referral_recommendations = models.IntegerField(default=0)

    # Usage stats
    avg_confidence = models.FloatField(default=0.0)
    total_alerts_generated = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_analysis_counter'
        unique_together = ('hospital', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['hospital', '-date']),
        ]

    def __str__(self):
        return f"{self.hospital.name} - {self.date}: {self.total_analyses} analyses"

    @classmethod
    def increment_analysis(cls, hospital: Hospital, analysis_type: str, **kwargs):
        """
        Increment counters for an analysis.

        Args:
            hospital: Hospital performing the analysis
            analysis_type: Type of analysis ('risk_prediction', 'cds_queries', etc.)
            **kwargs: Additional fields to update
        """
        today = timezone.now().date()
        counter, _ = cls.objects.get_or_create(hospital=hospital, date=today)

        counter.total_analyses += 1
        if analysis_type == 'risk_prediction':
            counter.risk_predictions += 1
        elif analysis_type == 'cds':
            counter.cds_queries += 1
        elif analysis_type == 'triage':
            counter.triage_assessments += 1
        elif analysis_type == 'similarity':
            counter.similarity_searches += 1
        elif analysis_type == 'referral':
            counter.referral_recommendations += 1

        # Update custom fields
        for key, value in kwargs.items():
            if hasattr(counter, key):
                setattr(counter, key, value)

        counter.save()


class AIAnalysisJob(models.Model):
    """
    Tracks the status of async AI analysis jobs (Celery tasks).

    Enables polling for long-running AI analysis operations.
    Frontend polls GET /ai/async-analysis/:job_id to track progress.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ai_jobs')
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='ai_jobs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    celery_task_id = models.CharField(max_length=255, unique=True, null=True, blank=True,
                                      help_text="Celery task ID for tracking")
    analysis_type = models.CharField(max_length=50, choices=AIAnalysis.ANALYSIS_TYPES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percent = models.IntegerField(default=0, help_text="0-100")
    current_step = models.CharField(max_length=100, blank=True,
                                    help_text="Current processing step (e.g., 'Running data agent')")

    # Result storage (populated when completed)
    analysis_result = models.OneToOneField(AIAnalysis, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='job')
    error_message = models.TextField(blank=True, help_text="Error message if job failed")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'api_ai_analysis_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"AI {self.analysis_type} job {self.id} ({self.status})"

    def is_finished(self):
        """Check if job is finished (completed or failed)."""
        return self.status in ('completed', 'failed', 'cancelled')

    def mark_processing(self):
        """Mark job as processing."""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save()

    def mark_completed(self, analysis_result):
        """Mark job as completed with result."""
        self.status = 'completed'
        self.analysis_result = analysis_result
        self.progress_percent = 100
        self.current_step = 'Completed'
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error_message):
        """Mark job as failed with error message."""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()

    def update_progress(self, percent, step=None):
        """Update job progress."""
        self.progress_percent = min(percent, 99)  # Cap at 99% until truly done
        if step:
            self.current_step = step
        self.save()


# Import AIDeploymentLog so Django can detect it for migrations
from api.models_deployment_log import AIDeploymentLog  # noqa: E402, F401


# ============================================================================
# Clinical Decision Support (CDS) Models
# ============================================================================

class ClinicalRule(models.Model):
    """
    Defines a clinical rule that triggers alerts.
    
    Examples:
    - Drug-drug interaction: warfarin + aspirin
    - Drug-allergy: amoxicillin for penicillin-allergic patient
    - Renal dosing: adjust for eGFR < 30
    - Duplicate therapy: two drugs in same class
    """
    
    RULE_TYPES = [
        ('drug_interaction', 'Drug-Drug Interaction'),
        ('drug_allergy', 'Drug-Allergy Contraindication'),
        ('renal_dosing', 'Renal Dose Adjustment'),
        ('duplicate_therapy', 'Duplicate Therapy'),
    ]
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Human-readable rule name")
    rule_type = models.CharField(max_length=50, choices=RULE_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    
    # Condition and action stored as JSON for flexibility
    # condition_json: dict with rule parameters (e.g. {"drug1": "warfarin", "drug2": "aspirin"})
    # action_json: dict with alert message and metadata
    condition_json = models.JSONField(default=_default_dict, help_text="Rule condition parameters")
    action_json = models.JSONField(default=_default_dict, help_text="Alert message and metadata")
    
    active = models.BooleanField(default=True, help_text="Enable/disable this rule")
    description = models.TextField(blank=True, help_text="Detailed description of the rule")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_rules"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['rule_type', 'active']),
            models.Index(fields=['severity']),
        ]
        ordering = ['rule_type', '-severity', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class CdsAlert(models.Model):
    """
    Records an alert triggered when a prescription or diagnosis is created.
    
    Alerts are informational and don't block prescription/diagnosis creation.
    They can be acknowledged by the doctor.
    """
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Link to encounter and triggered rule
    encounter = models.ForeignKey(
        Encounter, on_delete=models.CASCADE, related_name="cds_alerts"
    )
    rule = models.ForeignKey(
        ClinicalRule, on_delete=models.PROTECT, related_name="alerts"
    )
    
    # Prescription or diagnosis that triggered this alert (can be both)
    prescription = models.ForeignKey(
        Prescription, null=True, blank=True, on_delete=models.CASCADE, related_name="cds_alerts"
    )
    diagnosis = models.ForeignKey(
        Diagnosis, null=True, blank=True, on_delete=models.CASCADE, related_name="cds_alerts"
    )
    
    # Alert metadata
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField(help_text="Alert message to display to doctor")
    
    # Extra context (e.g. drug names, lab values, etc.)
    context_data = models.JSONField(
        default=_default_dict, help_text="Additional context for the alert (drug names, values, etc.)"
    )
    
    # Acknowledgment tracking
    acknowledged = models.BooleanField(default=False, help_text="Has doctor acknowledged this alert?")
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, 
        related_name="acknowledged_cds_alerts"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgment_notes = models.TextField(blank=True, help_text="Doctor's notes on acknowledgment")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['encounter', '-created_at']),
            models.Index(fields=['encounter', 'acknowledged']),
            models.Index(fields=['severity']),
            models.Index(fields=['rule', 'severity']),
        ]
        ordering = ['-severity', '-created_at']
    
    def __str__(self):
        return f"CDS Alert: {self.rule.name} (Encounter: {self.encounter.id})"
    
    def acknowledge(self, user, notes=""):
        """Mark alert as acknowledged by a doctor."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.acknowledgment_notes = notes
        self.save(update_fields=[
            'acknowledged', 'acknowledged_by', 'acknowledged_at', 'acknowledgment_notes'
        ])


# ============================================================================
# PHARMACY MODELS: Drug Inventory, Dispensation, Stock Tracking, Alerts
# ============================================================================


class DrugStock(models.Model):
    """
    Drug inventory tracked by batch.
    
    Each batch has a unique combination of drug, hospital, batch_number, and expiry_date.
    Quantity can be decremented as drugs are dispensed.
    """
    
    UNIT_CHOICES = [
        ('tablets', 'Tablets'),
        ('capsules', 'Capsules'),
        ('mL', 'Milliliters'),
        ('L', 'Liters'),
        ('grams', 'Grams'),
        ('mg', 'Milligrams'),
        ('vials', 'Vials'),
        ('ampoules', 'Ampoules'),
        ('units', 'Units'),
        ('patches', 'Patches'),
        ('tubes', 'Tubes'),
        ('inhalers', 'Inhalers'),
        ('sprays', 'Sprays'),
        ('drops', 'Drops'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='drug_stock')
    drug_name = models.CharField(max_length=200, help_text="Brand name or common name")
    generic_name = models.CharField(max_length=200, blank=True, help_text="Generic/active ingredient")
    batch_number = models.CharField(max_length=50, help_text="Manufacturer batch/lot number")
    quantity = models.PositiveIntegerField(help_text="Current quantity in stock")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, help_text="Unit of measurement")
    reorder_level = models.PositiveIntegerField(help_text="Minimum quantity before alert")
    expiry_date = models.DateField(help_text="Expiration date of batch")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pharmacy_drug_stock'
        unique_together = ('hospital', 'drug_name', 'batch_number', 'expiry_date')
        indexes = [
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['hospital', 'expiry_date']),
            models.Index(fields=['drug_name', 'hospital']),
        ]
    
    def __str__(self):
        return f"{self.drug_name} (Batch: {self.batch_number}) @ {self.hospital.name}"
    
    def is_low_stock(self):
        """Check if quantity is below reorder level."""
        return self.quantity < self.reorder_level
    
    def is_expiring_soon(self, days=30):
        """Check if expiry date is within specified days."""
        from datetime import timedelta
        cutoff = timezone.now().date() + timedelta(days=days)
        return self.expiry_date <= cutoff
    
    def is_expired(self):
        """Check if batch is already expired."""
        return self.expiry_date <= timezone.now().date()


class Dispensation(models.Model):
    """
    Record of medication dispensed to a patient.
    
    Immutable audit trail linking prescription → stock batch → quantity dispensed.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    prescription = models.OneToOneField(Prescription, on_delete=models.CASCADE, related_name='dispensation')
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.PROTECT, related_name='dispensations')
    quantity_dispensed = models.PositiveIntegerField(help_text="Quantity given to patient")
    dispensed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='dispensed_medications')
    dispensed_at = models.DateTimeField(auto_now_add=True)
    batch_notes = models.TextField(blank=True, help_text="Pharmacy notes on dispensation")
    
    class Meta:
        db_table = 'pharmacy_dispensation'
        indexes = [
            models.Index(fields=['drug_stock', '-dispensed_at']),
            models.Index(fields=['dispensed_by', '-dispensed_at']),
        ]
    
    def __str__(self):
        return f"Dispensed {self.quantity_dispensed}{self.drug_stock.unit} of {self.drug_stock.drug_name}"


class StockMovement(models.Model):
    """
    Audit trail for all stock changes.
    
    Tracks received, dispensed, adjusted, expired, and damaged movements.
    """
    
    MOVEMENT_TYPES = [
        ('received', 'Stock Received'),
        ('dispensed', 'Dispensed to Patient'),
        ('adjustment', 'Manual Adjustment'),
        ('expired', 'Expired/Destroyed'),
        ('damaged', 'Damaged'),
        ('transfer', 'Transfer to Another Hospital'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive = added, negative = removed")
    quantity_before = models.PositiveIntegerField(default=0, help_text="Stock quantity before movement")
    quantity_after = models.PositiveIntegerField(default=0, help_text="Stock quantity after movement")
    reason = models.TextField(blank=True, help_text="Reason for movement (adjustment reason, damaged qty, etc.)")
    performed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_movements')
    dispensation = models.ForeignKey(
        Dispensation, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Link to dispensation if movement_type=dispensed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pharmacy_stock_movement'
        indexes = [
            models.Index(fields=['drug_stock', '-created_at']),
            models.Index(fields=['movement_type', '-created_at']),
            models.Index(fields=['performed_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_movement_type_display()} of {self.quantity} units"


class StockAlert(models.Model):
    """
    Alert for low-stock or expiring medications.
    
    Persists alert history for compliance and clinical review.
    """
    
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Already Expired'),
    ]
    
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='stock_alerts')
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='acknowledged_stock_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pharmacy_stock_alert'
        indexes = [
            models.Index(fields=['hospital', 'status', '-created_at']),
            models.Index(fields=['drug_stock', '-created_at']),
            models.Index(fields=['alert_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.drug_stock.drug_name} @ {self.hospital.name}"
    
    def acknowledge(self, user):
        """Mark alert as acknowledged."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
    
    def resolve(self):
        """Mark alert as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])


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

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
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
        db_table = 'ai_model_version'
        ordering = ['-trained_at']
        indexes = [
            models.Index(fields=['model_type', 'is_production']),
            models.Index(fields=['version_tag']),
        ]

    def __str__(self):
        return f"{self.model_type} {self.version_tag} ({'PROD' if self.is_production else 'DRAFT'})"

