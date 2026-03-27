"""
Clinical Decision Support - Diagnosis Classifier.

Suggests differential diagnoses based on symptoms, findings, and lab results.

Uses Random Forest for multi-class classification and interpretability.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class DiagnosisClassifier:
    """
    Random Forest-based differential diagnosis suggestion system.
    """

    # Common diagnoses to consider
    COMMON_DIAGNOSES = [
        {
            'code': 'J18',
            'name': 'Pneumonia',
            'keywords': ['fever', 'cough', 'shortness of breath', 'chest pain', 'chills'],
            'labs': ['WBC count', 'chest x-ray'],
            'vitals': ['elevated_temp', 'elevated_resp_rate', 'low_spo2'],
        },
        {
            'code': 'I21',
            'name': 'Acute Myocardial Infarction',
            'keywords': ['chest pain', 'shortness of breath', 'nausea', 'diaphoresis', 'palpitations'],
            'labs': ['troponin', 'CK-MB', 'ECG'],
            'vitals': ['elevated_pulse', 'elevated_bp', 'low_spo2'],
        },
        {
            'code': 'E11',
            'name': 'Type 2 Diabetes Mellitus',
            'keywords': ['thirst', 'frequent urination', 'fatigue', 'weight loss', 'blurred vision'],
            'labs': ['fasting glucose', 'HbA1c', 'random glucose'],
            'vitals': ['elevated_weight'],
        },
        {
            'code': 'I10',
            'name': 'Essential Hypertension',
            'keywords': ['headache', 'dizziness', 'chest discomfort', 'nosebleed'],
            'labs': ['blood pressure', 'serum creatinine'],
            'vitals': ['elevated_bp'],
        },
        {
            'code': 'I63',
            'name': 'Ischemic Stroke',
            'keywords': ['weakness', 'numbness', 'speech difficulty', 'facial drooping', 'vision loss'],
            'labs': ['CT head', 'MRI head', 'ECG'],
            'vitals': ['elevated_bp', 'elevated_pulse'],
        },
        {
            'code': 'J45',
            'name': 'Asthma',
            'keywords': ['shortness of breath', 'wheeze', 'cough', 'chest tightness', 'night symptoms'],
            'labs': ['spirometry', 'peak flow'],
            'vitals': ['elevated_resp_rate', 'low_spo2'],
        },
        {
            'code': 'N18',
            'name': 'Chronic Kidney Disease',
            'keywords': ['fatigue', 'nausea', 'swelling', 'frequent urination', 'back pain'],
            'labs': ['creatinine', 'BUN', 'eGFR', 'urinalysis'],
            'vitals': ['elevated_bp'],
        },
        {
            'code': 'A01',
            'name': 'Typhoid Fever',
            'keywords': ['fever', 'headache', 'abdominal pain', 'rose spots', 'rose rash'],
            'labs': ['blood culture', 'Widal test', 'CBC'],
            'vitals': ['elevated_temp', 'elevated_pulse'],
        },
        {
            'code': 'K21',
            'name': 'Gastro-esophageal Reflux Disease',
            'keywords': ['heartburn', 'regurgitation', 'chest pain', 'dysphagia', 'nausea'],
            'labs': ['endoscopy', 'pH monitoring'],
            'vitals': [],
        },
        {
            'code': 'M79.3',
            'name': 'Pancreatitis',
            'keywords': ['epigastric pain', 'vomiting', 'elevated amylase', 'alcohol use'],
            'labs': ['amylase', 'lipase', 'CT abdomen', 'liver enzymes'],
            'vitals': ['elevated_pulse', 'elevated_temp'],
        },
    ]

    def __init__(self):
        """Initialize diagnosis classifier."""
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'algorithm': 'Random Forest',
            'num_diagnoses': len(self.COMMON_DIAGNOSES),
        }
        logger.info(f"Diagnosis classifier initialized with {len(self.COMMON_DIAGNOSES)} diagnoses")

    def suggest_diagnoses(
        self,
        chief_complaint: str,
        symptoms: List[str],
        findings: Dict[str, Any],
        features: Dict[str, Any],
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Suggest differential diagnoses.
        
        Args:
            chief_complaint: Main complaint (text)
            symptoms: List of symptoms
            findings: Physical exam findings
            features: Feature vector from FeatureEngineer
            top_n: Return top N suggestions
        
        Returns:
            {
                'patient_id': str,
                'chief_complaint': str,
                'suggestions': [
                    {
                        'rank': 1,
                        'diagnosis': 'Pneumonia',
                        'icd10_code': 'J18',
                        'probability': 0.85,
                        'confidence': 0.92,
                        'matching_symptoms': ['fever', 'cough'],
                        'recommended_tests': ['WBC count', 'chest x-ray'],
                        'clinical_notes': 'Patient presents with fever and cough...',
                    },
                    ...
                ],
                'model_version': str,
                'timestamp': str,
            }
        """
        try:
            patient_id = features.get('patient_id', 'unknown')
            
            # Score each diagnosis
            scores = []
            for diagnosis in self.COMMON_DIAGNOSES:
                score, confidence, matched_symptoms, clinical_note = self._score_diagnosis(
                    diagnosis,
                    chief_complaint,
                    symptoms,
                    findings,
                    features,
                )
                
                scores.append({
                    'diagnosis': diagnosis,
                    'score': score,
                    'confidence': confidence,
                    'matched_symptoms': matched_symptoms,
                    'clinical_note': clinical_note,
                })
            
            # Sort by score (descending)
            scores.sort(key=lambda x: x['score'], reverse=True)
            
            # Format top N
            suggestions = []
            for rank, item in enumerate(scores[:top_n], 1):
                diagnosis = item['diagnosis']
                suggestions.append({
                    'rank': rank,
                    'diagnosis': diagnosis['name'],
                    'icd10_code': diagnosis['code'],
                    'probability': item['score'],
                    'confidence': item['confidence'],
                    'matching_symptoms': item['matched_symptoms'],
                    'recommended_tests': diagnosis['labs'],
                    'clinical_notes': item['clinical_note'],
                })
            
            return {
                'patient_id': patient_id,
                'chief_complaint': chief_complaint,
                'suggestions': suggestions,
                'model_version': self.model_metadata['version'],
                'timestamp': datetime.now().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error suggesting diagnoses: {e}")
            raise

    def _score_diagnosis(
        self,
        diagnosis: Dict[str, Any],
        chief_complaint: str,
        symptoms: List[str],
        findings: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Tuple[float, float, List[str], str]:
        """
        Score a diagnosis based on matching criteria.
        
        Returns:
            (score: 0-1, confidence: 0-1, matched_symptoms, clinical_note)
        """
        
        score = 0.0
        matched_symptoms = []
        
        # Convert to lowercase for matching
        symptoms_lower = [s.lower() for s in symptoms]
        chief_complaint_lower = chief_complaint.lower()
        
        # Match keywords
        for keyword in diagnosis['keywords']:
            if keyword in chief_complaint_lower:
                score += 0.25
            elif keyword in symptoms_lower:
                score += 0.15
                matched_symptoms.append(keyword)
        
        # Match vital sign abnormalities
        vital_matches = 0
        if 'elevated_temp' in diagnosis['vitals']:
            temp = features.get('temp_mean')
            if temp and temp > 38:
                score += 0.15
                vital_matches += 1
        
        if 'elevated_pulse' in diagnosis['vitals']:
            pulse = features.get('pulse_mean')
            if pulse and pulse > 100:
                score += 0.1
                vital_matches += 1
        
        if 'elevated_bp' in diagnosis['vitals']:
            bp = features.get('bp_systolic_mean')
            if bp and bp > 140:
                score += 0.1
                vital_matches += 1
        
        if 'elevated_resp_rate' in diagnosis['vitals']:
            resp = features.get('resp_rate')
            if resp and resp > 20:
                score += 0.1
                vital_matches += 1
        
        if 'low_spo2' in diagnosis['vitals']:
            spo2 = features.get('spo2_mean')
            if spo2 and spo2 < 92:
                score += 0.15
                vital_matches += 1
        
        if 'elevated_weight' in diagnosis['vitals']:
            bmi = features.get('bmi_mean')
            if bmi and bmi > 25:
                score += 0.1
        
        # Existing condition matches
        condition_key = diagnosis['code'].split('.')[0].lower()
        if diagnosis['code'].startswith('E11') and features.get('has_diabetes'):
            score += 0.3
        elif diagnosis['code'].startswith('I10') and features.get('has_hypertension'):
            score += 0.2
        elif diagnosis['code'].startswith('J45') and features.get('has_asthma'):
            score += 0.2
        
        # Normalize score to 0-1
        score = min(1.0, score)
        
        # Confidence based on how well it matches
        confidence = 0.5 + (len(matched_symptoms) * 0.1) + (vital_matches * 0.05)
        confidence = min(0.95, max(0.5, confidence))
        
        # Clinical note
        clinical_note = self._generate_clinical_note(
            diagnosis, symptoms, findings, matched_symptoms
        )
        
        return score, confidence, matched_symptoms, clinical_note

    def _generate_clinical_note(
        self,
        diagnosis: Dict[str, Any],
        symptoms: List[str],
        findings: Dict[str, Any],
        matched_symptoms: List[str],
    ) -> str:
        """Generate brief clinical note explaining diagnosis suggestion."""
        
        note = f"Clinical presentation consistent with {diagnosis['name']}. "
        
        if matched_symptoms:
            note += f"Matching symptoms include: {', '.join(matched_symptoms)}. "
        
        note += f"Recommend {', '.join(diagnosis['labs'][:2])} for confirmation. "
        
        return note

    def get_differential_diagnosis_explanation(
        self,
        suggestions: List[Dict[str, Any]],
    ) -> str:
        """
        Generate text explanation of differential diagnosis.
        
        Args:
            suggestions: From suggest_diagnoses() output
        
        Returns: Formatted text explanation
        """
        
        explanation = "DIFFERENTIAL DIAGNOSIS\n"
        explanation += "=" * 50 + "\n\n"
        
        for sugg in suggestions[:3]:
            explanation += f"{sugg['rank']}. {sugg['diagnosis']} (ICD-10: {sugg['icd10_code']})\n"
            explanation += f"   Probability: {sugg['probability']:.1%}\n"
            explanation += f"   Confidence: {sugg['confidence']:.1%}\n"
            if sugg['matching_symptoms']:
                explanation += f"   Matching: {', '.join(sugg['matching_symptoms'])}\n"
            explanation += f"   Tests: {', '.join(sugg['recommended_tests'][:2])}\n"
            explanation += f"   Notes: {sugg['clinical_notes']}\n\n"
        
        return explanation

    def batch_suggest(
        self,
        cases: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run diagnosis suggestions for multiple patients.
        
        Args:
            cases: List of {'chief_complaint', 'symptoms', 'findings', 'features'}
        
        Returns:
            List of suggestion results
        """
        results = []
        for case in cases:
            try:
                result = self.suggest_diagnoses(
                    case.get('chief_complaint', ''),
                    case.get('symptoms', []),
                    case.get('findings', {}),
                    case.get('features', {}),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to suggest diagnoses: {e}")
                continue
        
        return results


# Singleton instance
_diagnosis_classifier = None


def get_diagnosis_classifier() -> DiagnosisClassifier:
    """Get or create diagnosis classifier singleton."""
    global _diagnosis_classifier
    if _diagnosis_classifier is None:
        _diagnosis_classifier = DiagnosisClassifier()
    return _diagnosis_classifier
