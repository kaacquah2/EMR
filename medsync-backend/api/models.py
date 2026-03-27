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
from datetime import datetime

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone

from core.models import Hospital, User
from patients.models import Patient

logger = logging.getLogger(__name__)


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
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ai_analyses')
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name='ai_analyses')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    analysis_type = models.CharField(max_length=50, choices=ANALYSIS_TYPES, default='comprehensive')
    
    # Analysis metadata
    overall_confidence = models.FloatField(default=0.0, help_text="0-1 confidence score")
    agents_executed = models.JSONField(default=list, help_text="Names of AI agents that executed")
    
    # Results summary
    clinical_summary = models.TextField(blank=True)
    recommended_actions = models.JSONField(default=list, help_text="List of recommended clinical actions")
    alerts = models.JSONField(default=list, help_text="Clinical alerts generated")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analysis request context
    chief_complaint = models.TextField(blank=True)
    additional_context = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'ai_analysis'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['analysis_type', '-created_at']),
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
        default=list,
        blank=True,
        help_text="List of factors that contributed to this prediction"
    )
    
    # Clinical recommendations
    recommendations = ArrayField(
        models.TextField(),
        default=list,
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
    matching_symptoms = models.JSONField(blank=True, default=list)
    recommended_tests = models.JSONField(blank=True, default=list)
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
        default=list,
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
    matching_conditions = models.JSONField(blank=True, default=list)
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
