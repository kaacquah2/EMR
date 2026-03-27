"""
Helper functions to save AI analysis results to the database.

Used by AI services and views to persist analysis results for auditing.
"""

import logging
from typing import Dict, Any, Optional

from api.models import (
    AIAnalysis,
    DiseaseRiskPrediction,
    DiagnosisSuggestion,
    TriageAssessment,
    PatientSimilarityMatch,
    ReferralRecommendation,
    AIAnalysisCounter,
)
from patients.models import Patient
from core.models import Hospital, User

logger = logging.getLogger(__name__)


def save_comprehensive_analysis(
    patient: Patient,
    hospital: Hospital,
    user: Optional[User],
    analysis_result: Dict[str, Any],
    chief_complaint: str = '',
) -> AIAnalysis:
    """
    Save complete multi-agent analysis to database.
    
    Args:
        patient: Patient analyzed
        hospital: Hospital context
        user: User who performed analysis
        analysis_result: Result dict from orchestrator
        chief_complaint: Chief complaint if provided
    
    Returns:
        AIAnalysis database object
    """
    try:
        # Create main analysis record
        analysis = AIAnalysis.objects.create(
            patient=patient,
            hospital=hospital,
            performed_by=user,
            analysis_type='comprehensive',
            overall_confidence=analysis_result.get('confidence_score', 0.0),
            agents_executed=analysis_result.get('agents_executed', []),
            clinical_summary=analysis_result.get('clinical_summary', ''),
            recommended_actions=analysis_result.get('recommended_actions', []),
            alerts=analysis_result.get('alerts', []),
            chief_complaint=chief_complaint,
        )
        
        # Save risk predictions
        risk_analysis = analysis_result.get('risk_analysis', {})
        if risk_analysis and 'predictions' in risk_analysis:
            for disease, pred in risk_analysis['predictions'].items():
                DiseaseRiskPrediction.objects.create(
                    analysis=analysis,
                    disease=disease,
                    risk_score=pred.get('risk_score', 0),
                    risk_category=pred.get('risk_category', 'low'),
                    confidence=pred.get('confidence', 0),
                    contributing_factors=risk_analysis.get('contributing_factors', []),
                    recommendations=risk_analysis.get('recommendations', []),
                )
        
        # Save diagnosis suggestions
        diagnosis_analysis = analysis_result.get('diagnosis_suggestions', {})
        if diagnosis_analysis and 'suggestions' in diagnosis_analysis:
            for rank, sugg in enumerate(diagnosis_analysis['suggestions'], 1):
                DiagnosisSuggestion.objects.create(
                    analysis=analysis,
                    rank=rank,
                    diagnosis=sugg.get('diagnosis', ''),
                    icd10_code=sugg.get('icd10_code', ''),
                    probability=sugg.get('probability', 0),
                    confidence=sugg.get('confidence', 0),
                    matching_symptoms=sugg.get('matching_symptoms', []),
                    recommended_tests=sugg.get('recommended_tests', []),
                    clinical_notes=sugg.get('clinical_notes', ''),
                )
        
        # Save triage assessment
        triage_assessment = analysis_result.get('triage_assessment', {})
        if triage_assessment:
            TriageAssessment.objects.create(
                analysis=analysis,
                triage_level=triage_assessment.get('triage_level', 'low'),
                triage_score=triage_assessment.get('score', 0),
                confidence=triage_assessment.get('confidence', 0),
                esi_level=triage_assessment.get('esi_level', 4),
                reason=triage_assessment.get('reason', ''),
                indicators=triage_assessment.get('indicators', []),
                recommended_action=triage_assessment.get('recommended_action', ''),
            )
        
        # Save similar patients (if available)
        similar_patients = analysis_result.get('similar_patients', {})
        if similar_patients and 'similar_patients' in similar_patients:
            for rank, match in enumerate(similar_patients['similar_patients'], 1):
                try:
                    similar_patient = Patient.objects.get(id=match.get('patient_id'))
                    PatientSimilarityMatch.objects.create(
                        analysis=analysis,
                        similar_patient=similar_patient,
                        rank=rank,
                        similarity_score=match.get('similarity_score', 0),
                        matching_conditions=match.get('conditions', []),
                        treatment_outcome=match.get('treatment_outcome'),
                        outcome_success_rate=match.get('outcome_success_rate'),
                    )
                except Patient.DoesNotExist:
                    logger.warning(f"Similar patient {match.get('patient_id')} not found")
        
        # Save referral recommendations (if available)
        referral_recs = analysis_result.get('referral_recommendations', {})
        if referral_recs and 'recommended_hospitals' in referral_recs:
            for rank, rec in enumerate(referral_recs['recommended_hospitals'], 1):
                try:
                    rec_hospital = Hospital.objects.get(id=rec.get('hospital_id'))
                    ReferralRecommendation.objects.create(
                        analysis=analysis,
                        recommended_hospital=rec_hospital,
                        rank=rank,
                        specialty_match=rec.get('specialty_match', 0),
                        bed_availability=rec.get('bed_availability'),
                        distance_km=rec.get('distance_km'),
                        success_rate=rec.get('success_rate'),
                        reason=rec.get('reason', ''),
                    )
                except Hospital.DoesNotExist:
                    logger.warning(f"Recommended hospital {rec.get('hospital_id')} not found")
        
        # Update usage counter
        AIAnalysisCounter.increment_analysis(
            hospital=hospital,
            analysis_type='comprehensive',
            avg_confidence=analysis.overall_confidence,
            total_alerts_generated=len(analysis.alerts),
        )
        
        logger.info(f"Saved comprehensive analysis {analysis.id} for patient {patient.id}")
        return analysis
    
    except Exception as e:
        logger.error(f"Error saving comprehensive analysis: {e}")
        raise


def save_risk_prediction(
    patient: Patient,
    hospital: Hospital,
    user: Optional[User],
    prediction_result: Dict[str, Any],
) -> AIAnalysis:
    """Save risk prediction analysis."""
    try:
        analysis = AIAnalysis.objects.create(
            patient=patient,
            hospital=hospital,
            performed_by=user,
            analysis_type='risk_prediction',
            overall_confidence=prediction_result.get('model_version', ''),
            agents_executed=['prediction_agent'],
            clinical_summary=f"Risk prediction for {prediction_result.get('top_risk_disease', 'unknown')}",
            recommended_actions=prediction_result.get('recommendations', []),
        )
        
        # Save disease predictions
        for disease, pred in prediction_result.get('predictions', {}).items():
            DiseaseRiskPrediction.objects.create(
                analysis=analysis,
                disease=disease,
                risk_score=pred.get('risk_score', 0),
                risk_category=pred.get('risk_category', 'low'),
                confidence=pred.get('confidence', 0),
            )
        
        AIAnalysisCounter.increment_analysis(hospital, 'risk_prediction')
        logger.info(f"Saved risk prediction for patient {patient.id}")
        return analysis
    
    except Exception as e:
        logger.error(f"Error saving risk prediction: {e}")
        raise


def save_diagnosis_suggestions(
    patient: Patient,
    hospital: Hospital,
    user: Optional[User],
    suggestion_result: Dict[str, Any],
) -> AIAnalysis:
    """Save CDS diagnosis suggestions."""
    try:
        analysis = AIAnalysis.objects.create(
            patient=patient,
            hospital=hospital,
            performed_by=user,
            analysis_type='clinical_decision_support',
            agents_executed=['diagnosis_agent'],
            chief_complaint=suggestion_result.get('chief_complaint', ''),
            clinical_summary='Clinical decision support - differential diagnosis',
        )
        
        # Save diagnosis suggestions
        for rank, sugg in enumerate(suggestion_result.get('suggestions', []), 1):
            DiagnosisSuggestion.objects.create(
                analysis=analysis,
                rank=rank,
                diagnosis=sugg.get('diagnosis', ''),
                icd10_code=sugg.get('icd10_code', ''),
                probability=sugg.get('probability', 0),
                confidence=sugg.get('confidence', 0),
                matching_symptoms=sugg.get('matching_symptoms', []),
                recommended_tests=sugg.get('recommended_tests', []),
                clinical_notes=sugg.get('clinical_notes', ''),
            )
        
        AIAnalysisCounter.increment_analysis(hospital, 'cds')
        logger.info(f"Saved diagnosis suggestions for patient {patient.id}")
        return analysis
    
    except Exception as e:
        logger.error(f"Error saving diagnosis suggestions: {e}")
        raise


def save_triage_assessment(
    patient: Patient,
    hospital: Hospital,
    user: Optional[User],
    triage_result: Dict[str, Any],
) -> AIAnalysis:
    """Save triage assessment."""
    try:
        analysis = AIAnalysis.objects.create(
            patient=patient,
            hospital=hospital,
            performed_by=user,
            analysis_type='triage',
            agents_executed=['triage_agent'],
            overall_confidence=triage_result.get('confidence', 0),
            alerts=[f"Triage: {triage_result.get('triage_level', 'unknown').upper()}"],
            recommended_actions=[triage_result.get('recommended_action', '')],
        )
        
        # Save triage
        TriageAssessment.objects.create(
            analysis=analysis,
            triage_level=triage_result.get('triage_level', 'low'),
            triage_score=triage_result.get('score', 0),
            confidence=triage_result.get('confidence', 0),
            esi_level=triage_result.get('esi_level', 4),
            reason=triage_result.get('reason', ''),
            indicators=triage_result.get('indicators', []),
            recommended_action=triage_result.get('recommended_action', ''),
        )
        
        AIAnalysisCounter.increment_analysis(hospital, 'triage')
        logger.info(f"Saved triage assessment for patient {patient.id}")
        return analysis
    
    except Exception as e:
        logger.error(f"Error saving triage assessment: {e}")
        raise
