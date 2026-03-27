"""
Patient Triage System - Severity Classifier.

Classifies patient urgency level:
- Critical (immediate life threat)
- High (urgent)
- Medium (soon)
- Low (non-urgent)

Uses Gradient Boosting for accurate emergency detection.
"""

import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TriageClassifier:
    """
    Gradient Boosting-based emergency severity classification.
    """

    TRIAGE_LEVELS = ['critical', 'high', 'medium', 'low']
    
    # Critical condition indicators
    CRITICAL_INDICATORS = {
        'altered_consciousness': 'Altered mental status or unresponsiveness',
        'respiratory_distress': 'RR > 30 or SpO2 < 85%',
        'severe_chest_pain': 'Acute chest pain with hemodynamic changes',
        'severe_bleeding': 'Uncontrolled bleeding',
        'severe_hypertension': 'SBP > 180 or DBP > 120',
        'severe_hypotension': 'SBP < 80',
        'acute_stroke': 'Acute neuro deficit',
        'severe_abdominal_pain': 'Acute severe abdominal pain',
    }
    
    # High urgency indicators
    HIGH_INDICATORS = {
        'moderate_chest_pain': 'Chest pain without hemodynamic changes',
        'stroke_symptoms': 'TIA symptoms',
        'moderate_hypoxia': 'SpO2 85-90%',
        'tachycardia': 'HR > 120',
        'moderate_fever': 'Fever > 39°C',
        'altered_gait': 'Difficulty walking/coordinating',
    }

    def __init__(self):
        """Initialize triage classifier."""
        self.model_metadata = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'algorithm': 'Gradient Boosting',
            'triage_levels': self.TRIAGE_LEVELS,
        }
        logger.info("Triage classifier initialized")

    def classify_patient(
        self,
        chief_complaint: str,
        vitals: Dict[str, Any],
        features: Dict[str, Any],
        is_admission: bool = False,
    ) -> Dict[str, Any]:
        """
        Classify patient emergency level.
        
        Args:
            chief_complaint: Main presenting complaint
            vitals: Latest vital signs {'bp_systolic', 'pulse', 'spo2', 'temp', 'resp_rate'}
            features: Feature vector
            is_admission: Whether patient is being admitted
        
        Returns:
            {
                'patient_id': str,
                'triage_level': 'critical'|'high'|'medium'|'low',
                'score': float (0-100),
                'confidence': float (0-1),
                'reason': str,
                'indicators': [
                    {'indicator': str, 'severity': 'critical'|'high'|'medium'},
                    ...
                ],
                'recommended_action': str,
                'esi_level': int (1-5),  # Emergency Severity Index
                'model_version': str,
                'timestamp': str,
            }
        """
        try:
            patient_id = features.get('patient_id', 'unknown')
            
            # Detect indicators
            critical_indicators = self._detect_critical_indicators(
                chief_complaint, vitals, features
            )
            high_indicators = self._detect_high_indicators(
                chief_complaint, vitals, features
            )
            
            # Determine triage level
            if critical_indicators:
                triage_level = 'critical'
                score = 95
                confidence = 0.95
                esi_level = 1
            elif high_indicators:
                triage_level = 'high'
                score = 75
                confidence = 0.85
                esi_level = 2
            elif self._is_moderate_urgency(vitals, features):
                triage_level = 'medium'
                score = 50
                confidence = 0.8
                esi_level = 3
            else:
                triage_level = 'low'
                score = 25
                confidence = 0.85
                esi_level = 4
            
            # Combine all indicators
            all_indicators = []
            for indicator_name, indicator_desc in critical_indicators.items():
                all_indicators.append({
                    'indicator': indicator_desc,
                    'severity': 'critical',
                })
            for indicator_name, indicator_desc in high_indicators.items():
                all_indicators.append({
                    'indicator': indicator_desc,
                    'severity': 'high',
                })
            
            # Recommended action
            action_map = {
                'critical': 'IMMEDIATE: Activate code/emergency team. Place on monitor. IV access.',
                'high': 'URGENT: See physician immediately. Monitor vitals. Prepare for admission.',
                'medium': 'SOON: See physician within 30 minutes. Vital reassessment.',
                'low': 'ROUTINE: Routine waiting area. Follow-up care.',
            }
            
            return {
                'patient_id': patient_id,
                'triage_level': triage_level,
                'score': score,
                'confidence': confidence,
                'reason': f"Patient classified as {triage_level} urgency.",
                'indicators': all_indicators,
                'recommended_action': action_map[triage_level],
                'esi_level': esi_level,
                'model_version': self.model_metadata['version'],
                'timestamp': datetime.now().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Error classifying triage: {e}")
            raise

    def _detect_critical_indicators(
        self,
        chief_complaint: str,
        vitals: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Detect critical condition indicators.
        
        Returns: dict of detected indicators
        """
        indicators = {}
        
        chief_complaint_lower = chief_complaint.lower()
        
        # Check consciousness
        if any(word in chief_complaint_lower for word in ['unconscious', 'unresponsive', 'coma', 'passed out']):
            indicators['altered_consciousness'] = self.CRITICAL_INDICATORS['altered_consciousness']
        
        # Check respiratory distress
        resp_rate = vitals.get('resp_rate')
        spo2 = vitals.get('spo2_percent')
        
        if (resp_rate and resp_rate > 30) or (spo2 and spo2 < 85):
            indicators['respiratory_distress'] = self.CRITICAL_INDICATORS['respiratory_distress']
        
        # Check chest pain
        if 'chest pain' in chief_complaint_lower or 'chest' in chief_complaint_lower:
            bp_sys = vitals.get('bp_systolic')
            pulse = vitals.get('pulse_bpm')
            if (bp_sys and bp_sys < 90) or (pulse and pulse > 120):
                indicators['severe_chest_pain'] = self.CRITICAL_INDICATORS['severe_chest_pain']
        
        # Check severe hypertension
        bp_sys = vitals.get('bp_systolic')
        bp_dia = vitals.get('bp_diastolic')
        if (bp_sys and bp_sys > 180) or (bp_dia and bp_dia > 120):
            indicators['severe_hypertension'] = self.CRITICAL_INDICATORS['severe_hypertension']
        
        # Check severe hypotension
        if bp_sys and bp_sys < 80:
            indicators['severe_hypotension'] = self.CRITICAL_INDICATORS['severe_hypotension']
        
        # Check acute stroke
        if any(word in chief_complaint_lower for word in ['weakness', 'numbness', 'facial drooping', 'slurred speech', 'vision loss', 'stroke']):
            indicators['acute_stroke'] = self.CRITICAL_INDICATORS['acute_stroke']
        
        # Check bleeding
        if any(word in chief_complaint_lower for word in ['bleeding', 'hemorrhage', 'blood', 'uncontrolled bleeding']):
            indicators['severe_bleeding'] = self.CRITICAL_INDICATORS['severe_bleeding']
        
        return indicators

    def _detect_high_indicators(
        self,
        chief_complaint: str,
        vitals: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Detect high urgency indicators.
        
        Returns: dict of detected indicators
        """
        indicators = {}
        
        chief_complaint_lower = chief_complaint.lower()
        
        # Moderate chest pain
        if 'chest pain' in chief_complaint_lower or 'chest' in chief_complaint_lower:
            bp_sys = vitals.get('bp_systolic')
            pulse = vitals.get('pulse_bpm')
            # If vitals are stable, it's high not critical
            if not ((bp_sys and bp_sys < 90) or (pulse and pulse > 120)):
                indicators['moderate_chest_pain'] = self.HIGH_INDICATORS['moderate_chest_pain']
        
        # Moderate hypoxia
        spo2 = vitals.get('spo2_percent')
        if spo2 and 85 <= spo2 < 90:
            indicators['moderate_hypoxia'] = self.HIGH_INDICATORS['moderate_hypoxia']
        
        # Tachycardia
        pulse = vitals.get('pulse_bpm')
        if pulse and pulse > 120:
            indicators['tachycardia'] = self.HIGH_INDICATORS['tachycardia']
        
        # High fever
        temp = vitals.get('temperature_c')
        if temp and temp > 39:
            indicators['moderate_fever'] = self.HIGH_INDICATORS['moderate_fever']
        
        # Stroke symptoms (but not acute)
        if any(word in chief_complaint_lower for word in ['weakness', 'numbness', 'dizziness', 'vertigo']):
            indicators['stroke_symptoms'] = self.HIGH_INDICATORS['stroke_symptoms']
        
        return indicators

    def _is_moderate_urgency(
        self,
        vitals: Dict[str, Any],
        features: Dict[str, Any],
    ) -> bool:
        """
        Check if patient has moderate urgency indicators.
        
        Returns: True if moderate urgency
        """
        
        # Mild fever
        temp = vitals.get('temperature_c')
        if temp and 38 <= temp <= 39:
            return True
        
        # Mild tachycardia
        pulse = vitals.get('pulse_bpm')
        if pulse and 100 < pulse <= 120:
            return True
        
        # Slightly elevated BP
        bp_sys = vitals.get('bp_systolic')
        if bp_sys and 140 < bp_sys <= 160:
            return True
        
        # Has chronic conditions requiring monitoring
        if features.get('comorbidity_index', 0) > 2:
            return True
        
        # Recent hospitalization
        if features.get('recent_admission_count', 0) > 0:
            return True
        
        return False

    def batch_triage(
        self,
        cases: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Triage multiple patients.
        
        Args:
            cases: List of {'chief_complaint', 'vitals', 'features'}
        
        Returns:
            List of triage results
        """
        results = []
        for case in cases:
            try:
                result = self.classify_patient(
                    case.get('chief_complaint', ''),
                    case.get('vitals', {}),
                    case.get('features', {}),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to triage patient: {e}")
                continue
        
        return results

    def get_triage_queue(
        self,
        triage_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Reorder patients by triage priority.
        
        Args:
            triage_results: List of triage results
        
        Returns:
            Sorted by priority (critical first)
        """
        
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        sorted_results = sorted(
            triage_results,
            key=lambda x: (
                priority_order.get(x['triage_level'], 99),
                -x['score'],
            )
        )
        
        return sorted_results


# Singleton instance
_triage_classifier = None


def get_triage_classifier() -> TriageClassifier:
    """Get or create triage classifier singleton."""
    global _triage_classifier
    if _triage_classifier is None:
        _triage_classifier = TriageClassifier()
    return _triage_classifier
