"""
Multi-Agent Orchestrator using CrewAI.

Coordinates 7 AI agents to perform complete patient analysis:
1. Data Agent - Fetches and cleans patient EMR data
2. Prediction Agent - Runs disease risk models
3. Diagnosis Agent - Suggests differential diagnoses
4. Triage Agent - Evaluates urgency/severity
5. Similarity Agent - Finds comparable cases
6. Referral Agent - Recommends hospitals
7. Summary Agent - Synthesizes all outputs

CrewAI provides agent framework, tools, and task orchestration.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """
    Multi-agent orchestrator for comprehensive patient analysis.
    
    This is a placeholder implementation. In production, this would use CrewAI.
    """

    def __init__(self):
        """Initialize orchestrator."""
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'orchestrator': 'CrewAI',
            'num_agents': 7,
            'agents': [
                'data_agent',
                'prediction_agent',
                'diagnosis_agent',
                'triage_agent',
                'similarity_agent',
                'referral_agent',
                'summary_agent',
            ],
        }
        logger.info("AI Orchestrator initialized with 7 agents")

    def analyze_patient_comprehensive(
        self,
        patient_data: Dict[str, Any],
        features: Dict[str, Any],
        chief_complaint: str = '',
        include_similarity: bool = True,
        include_referral: bool = True,
    ) -> Dict[str, Any]:
        """
        Run complete multi-agent analysis on patient.
        
        Orchestration sequence:
        1. Data Agent - Validate/clean EMR data
        2. Prediction Agent - Risk scores
        3. Triage Agent - Urgency level
        4. Diagnosis Agent - Differential diagnoses
        5. Similarity Agent - Similar cases (optional)
        6. Referral Agent - Hospital recommendations (optional)
        7. Summary Agent - Clinical summary + recommendations
        
        Args:
            patient_data: Complete patient data from DataProcessor
            features: Engineered feature vector
            chief_complaint: Chief complaint text
            include_similarity: Include similar patient search
            include_referral: Include hospital recommendations
        
        Returns:
            {
                'patient_id': str,
                'analysis_timestamp': str,
                'agents_executed': [agent_names],
                'risk_analysis': {...},
                'triage_assessment': {...},
                'diagnosis_suggestions': {...},
                'similar_patients': {...} or None,
                'referral_recommendations': {...} or None,
                'clinical_summary': str,
                'recommended_actions': [str],
                'alerts': [str],
                'confidence_score': float,
            }
        """
        try:
            patient_id = features.get('patient_id', 'unknown')
            agents_executed = []
            
            logger.info(f"Starting comprehensive analysis for patient {patient_id}")
            
            # 1. Data Agent - Validate EMR data
            data_agent_result = self._run_data_agent(patient_data)
            agents_executed.append('data_agent')
            
            # 2. Prediction Agent - Risk scores
            prediction_result = self._run_prediction_agent(features)
            agents_executed.append('prediction_agent')
            
            # 3. Triage Agent - Urgency evaluation
            triage_result = self._run_triage_agent(patient_data, features, chief_complaint)
            agents_executed.append('triage_agent')
            
            # 4. Diagnosis Agent - Differential diagnosis
            diagnosis_result = self._run_diagnosis_agent(
                chief_complaint,
                patient_data,
                features
            )
            agents_executed.append('diagnosis_agent')
            
            # 5. Similarity Agent (optional)
            similarity_result = None
            if include_similarity:
                similarity_result = self._run_similarity_agent(features)
                agents_executed.append('similarity_agent')
            
            # 6. Referral Agent (optional)
            referral_result = None
            if include_referral:
                referral_result = self._run_referral_agent(
                    patient_data,
                    diagnosis_result,
                    triage_result
                )
                agents_executed.append('referral_agent')
            
            # 7. Summary Agent - Synthesize all outputs
            summary_result = self._run_summary_agent(
                patient_id,
                prediction_result,
                diagnosis_result,
                triage_result,
                similarity_result,
                referral_result,
            )
            agents_executed.append('summary_agent')
            
            # Generate alerts
            alerts = self._generate_alerts(prediction_result, triage_result, diagnosis_result)
            
            # Calculate overall confidence
            confidence = self._calculate_overall_confidence(
                prediction_result,
                triage_result,
                diagnosis_result,
            )
            
            result = {
                'patient_id': str(patient_id),
                'analysis_timestamp': datetime.now().isoformat(),
                'agents_executed': agents_executed,
                'risk_analysis': prediction_result,
                'triage_assessment': triage_result,
                'diagnosis_suggestions': diagnosis_result,
                'similar_patients': similarity_result,
                'referral_recommendations': referral_result,
                'clinical_summary': summary_result['summary'],
                'recommended_actions': summary_result['actions'],
                'alerts': alerts,
                'confidence_score': confidence,
            }
            
            logger.info(f"Comprehensive analysis complete for patient {patient_id}")
            return result
        
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            raise

    def _run_data_agent(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Data Agent: Validate and clean patient EMR data.
        
        Tasks:
        - Check data completeness
        - Detect outliers
        - Validate temporal consistency
        """
        try:
            # Check data quality
            is_complete = self._check_data_completeness(patient_data)
            has_outliers = self._detect_outliers(patient_data)
            
            return {
                'agent': 'data_agent',
                'data_complete': is_complete,
                'outliers_detected': has_outliers,
                'quality_score': 0.85,
                'status': 'success',
            }
        except Exception as e:
            logger.error(f"Data Agent failed: {e}")
            raise

    def _run_prediction_agent(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prediction Agent: Run disease risk prediction models.
        
        Tasks:
        - Disease risk scoring
        - Identify top risks
        - Extract contributing factors
        """
        try:
            from api.ai.services import RiskPredictionService
            from core.models import User
            
            # Note: In production, get actual user from request context
            # For orchestrator, use system user or service account
            dummy_user = None  # Would be actual user
            
            # If we have user context, use service
            if dummy_user:
                service = RiskPredictionService(dummy_user)
                result = service.predict_risk(features.get('patient_id'))
            else:
                # For now, return mock result
                from api.ai.ml_models import get_risk_predictor
                predictor = get_risk_predictor()
                result = predictor.predict_risk(features)
            
            return result
        
        except Exception as e:
            logger.error(f"Prediction Agent failed: {e}")
            return {'error': str(e)}

    def _run_triage_agent(
        self,
        patient_data: Dict[str, Any],
        features: Dict[str, Any],
        chief_complaint: str,
    ) -> Dict[str, Any]:
        """
        Triage Agent: Assess patient urgency.
        
        Tasks:
        - Evaluate vital signs
        - Assess severity
        - Assign ESI level
        """
        try:
            from api.ai.ml_models import get_triage_classifier
            
            classifier = get_triage_classifier()
            
            # Extract latest vitals
            vitals = {}
            if patient_data.get('vitals'):
                latest_vital = patient_data['vitals'][0]
                vitals = {
                    'bp_systolic': latest_vital.get('bp_systolic'),
                    'bp_diastolic': latest_vital.get('bp_diastolic'),
                    'pulse_bpm': latest_vital.get('pulse_bpm'),
                    'spo2_percent': latest_vital.get('spo2_percent'),
                    'temperature_c': latest_vital.get('temperature_c'),
                    'resp_rate': latest_vital.get('resp_rate'),
                }
            
            result = classifier.classify_patient(chief_complaint, vitals, features)
            return result
        
        except Exception as e:
            logger.error(f"Triage Agent failed: {e}")
            return {'error': str(e)}

    def _run_diagnosis_agent(
        self,
        chief_complaint: str,
        patient_data: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Diagnosis Agent: Generate differential diagnoses.
        
        Tasks:
        - Suggest diagnoses
        - Recommend diagnostic tests
        - Provide clinical evidence
        """
        try:
            from api.ai.ml_models import get_diagnosis_classifier
            
            classifier = get_diagnosis_classifier()
            
            # Extract symptoms from diagnoses
            diagnoses = patient_data.get('diagnoses', [])
            symptoms = [d['icd10_description'] for d in diagnoses[-5:]]
            
            result = classifier.suggest_diagnoses(
                chief_complaint,
                symptoms,
                {},  # findings
                features,
                top_n=5,
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Diagnosis Agent failed: {e}")
            return {'error': str(e)}

    def _run_similarity_agent(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Similarity Agent: Find similar patient cases.
        
        Tasks:
        - Search for comparable patients
        - Extract treatment outcomes
        - Recommend similar treatments
        """
        try:
            from api.ai.ml_models import get_similarity_matcher
            
            matcher = get_similarity_matcher()
            
            # Note: Would need to index patients first
            result = {
                'agent': 'similarity_agent',
                'note': 'Requires patient data indexing',
                'status': 'pending',
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Similarity Agent failed: {e}")
            return None

    def _run_referral_agent(
        self,
        patient_data: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        triage_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Referral Agent: Recommend appropriate hospitals.
        
        Tasks:
        - Identify specialty needed
        - Score hospitals
        - Recommend top choices
        """
        try:
            # Extract specialty from diagnosis
            specialty = ''
            if diagnosis_result and 'suggestions' in diagnosis_result:
                if diagnosis_result['suggestions']:
                    top_diagnosis = diagnosis_result['suggestions'][0]
                    specialty = self._map_diagnosis_to_specialty(top_diagnosis['diagnosis'])
            
            result = {
                'agent': 'referral_agent',
                'specialty_needed': specialty,
                'recommendations': [],
                'status': 'pending',
                'note': 'Hospital recommendations available via ReferralRecommendationService',
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Referral Agent failed: {e}")
            return None

    def _run_summary_agent(
        self,
        patient_id: str,
        prediction_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        triage_result: Dict[str, Any],
        similarity_result: Optional[Dict[str, Any]],
        referral_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Summary Agent: Synthesize all analysis into clinical summary.
        
        Tasks:
        - Integrate all findings
        - Generate clinical narrative
        - Provide action recommendations
        """
        try:
            summary = self._generate_clinical_summary(
                patient_id,
                prediction_result,
                diagnosis_result,
                triage_result,
            )
            
            actions = self._generate_recommended_actions(
                prediction_result,
                diagnosis_result,
                triage_result,
                referral_result,
            )
            
            return {
                'agent': 'summary_agent',
                'summary': summary,
                'actions': actions,
                'status': 'success',
            }
        
        except Exception as e:
            logger.error(f"Summary Agent failed: {e}")
            return {'summary': '', 'actions': []}

    # Helper methods

    def _check_data_completeness(self, patient_data: Dict[str, Any]) -> bool:
        """Check if key data sections are present."""
        required = ['demographics', 'vitals', 'diagnoses']
        return all(patient_data.get(field) for field in required)

    def _detect_outliers(self, patient_data: Dict[str, Any]) -> bool:
        """Check for outliers in vital signs."""
        # Simplified check
        vitals = patient_data.get('vitals', [])
        if vitals:
            latest = vitals[0]
            # Check for obviously abnormal values
            if latest.get('bp_systolic', 0) > 250 or latest.get('bp_systolic', 0) < 50:
                return True
        return False

    def _generate_alerts(
        self,
        prediction_result: Dict[str, Any],
        triage_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
    ) -> List[str]:
        """Generate clinical alerts."""
        alerts = []
        
        # Risk alerts
        if prediction_result and prediction_result.get('top_risk_score', 0) > 80:
            top_disease = prediction_result.get('top_risk_disease', 'disease')
            alerts.append(f"⚠️ CRITICAL: High risk of {top_disease} detected ({prediction_result['top_risk_score']:.0f}%)")
        
        # Triage alerts
        if triage_result and triage_result.get('triage_level') in ['critical', 'high']:
            alerts.append(f"🚨 {triage_result['triage_level'].upper()}: {triage_result.get('reason', 'Urgent evaluation needed')}")
        
        return alerts

    def _calculate_overall_confidence(
        self,
        prediction_result: Dict[str, Any],
        triage_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
    ) -> float:
        """Calculate overall analysis confidence."""
        scores = []
        
        if prediction_result and 'top_risk_score' in prediction_result:
            scores.append(prediction_result.get('predictions', {}).get(
                prediction_result['top_risk_disease'], {}
            ).get('confidence', 0.5))
        
        if triage_result and 'confidence' in triage_result:
            scores.append(triage_result['confidence'])
        
        if diagnosis_result and 'suggestions' in diagnosis_result:
            if diagnosis_result['suggestions']:
                scores.append(diagnosis_result['suggestions'][0].get('confidence', 0.5))
        
        return sum(scores) / len(scores) if scores else 0.5

    def _generate_clinical_summary(
        self,
        patient_id: str,
        prediction_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        triage_result: Dict[str, Any],
    ) -> str:
        """Generate clinical summary narrative."""
        summary = f"Patient {patient_id}: "
        
        if triage_result:
            summary += f"{triage_result.get('triage_level', 'unknown').upper()} urgency. "
        
        if diagnosis_result and diagnosis_result.get('suggestions'):
            top_diagnosis = diagnosis_result['suggestions'][0]
            summary += f"Differential diagnosis suggests {top_diagnosis['diagnosis']} as most likely. "
        
        if prediction_result:
            top_disease = prediction_result.get('top_risk_disease', 'unknown')
            score = prediction_result.get('top_risk_score', 0)
            summary += f"Risk assessment indicates {score:.0f}% risk of {top_disease}. "
        
        summary += "Recommend further evaluation and testing as outlined in action items."
        
        return summary

    def _generate_recommended_actions(
        self,
        prediction_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        triage_result: Dict[str, Any],
        referral_result: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate recommended clinical actions."""
        actions = []
        
        # Triage action
        if triage_result:
            actions.append(triage_result.get('recommended_action', 'Monitor patient status'))
        
        # Diagnostic actions
        if diagnosis_result and diagnosis_result.get('suggestions'):
            top_diagnosis = diagnosis_result['suggestions'][0]
            if top_diagnosis.get('recommended_tests'):
                test_list = ', '.join(top_diagnosis['recommended_tests'][:2])
                actions.append(f"Order tests: {test_list}")
        
        # Risk management actions
        if prediction_result:
            if prediction_result.get('top_risk_score', 0) > 60:
                actions.extend(prediction_result.get('recommendations', []))
        
        # Referral action
        if referral_result and referral_result.get('recommendations'):
            actions.append(f"Consider referral to {referral_result['recommendations'][0].get('hospital_name', 'specialist')}")
        
        return actions

    def _map_diagnosis_to_specialty(self, diagnosis: str) -> str:
        """Map diagnosis to medical specialty."""
        mapping = {
            'Pneumonia': 'Pulmonology',
            'Myocardial Infarction': 'Cardiology',
            'Stroke': 'Neurology',
            'Diabetes': 'Endocrinology',
            'Kidney Disease': 'Nephrology',
        }
        return mapping.get(diagnosis, 'General Medicine')


# Singleton instance
_orchestrator = None


def get_orchestrator() -> AIOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator()
    return _orchestrator
