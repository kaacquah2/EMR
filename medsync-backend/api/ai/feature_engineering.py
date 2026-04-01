"""
Feature Engineering for AI Models.

Transforms raw patient data into feature vectors suitable for ML models.

Features engineered:
- Demographics (age groups, gender encoding)
- Clinical indicators (comorbidity index, risk factors)
- Vital trends (moving averages, trends)
- Lab value patterns
- Medication complexity scores
- Allergy severity indices
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
import logging
import math
import statistics

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Converts raw patient data into feature vectors for ML models.
    """

    # ICD-10 codes for common conditions
    CONDITIONS = {
        'heart_disease': ['I10', 'I11', 'I12', 'I13', 'I50', 'I21', 'I24', 'I25'],
        'diabetes': ['E10', 'E11', 'E12', 'E13', 'E14'],
        'hypertension': ['I10', 'I11', 'I12', 'I13'],
        'stroke': ['I63', 'I64', 'I61', 'I60'],
        'pneumonia': ['J13', 'J14', 'J15', 'J16', 'J17', 'J18'],
        'kidney_disease': ['N02', 'N03', 'N18', 'N19'],
        'copd': ['J41', 'J42', 'J43', 'J44'],
        'cancer': ['C00', 'C01', 'C02'],  # Prefix match for all cancers
        'asthma': ['J45'],
    }

    # Lab value ranges for normal/abnormal detection
    LAB_RANGES = {
        'HbA1c': {'normal': (0, 5.7), 'prediabetic': (5.7, 6.5), 'diabetic': (6.5, 20)},
        'Fasting Blood Glucose': {'normal': (0, 100), 'prediabetic': (100, 126), 'diabetic': (126, 500)},
        'Hemoglobin': {'low': (0, 12), 'normal': (12, 17.5), 'high': (17.5, 25)},
        'Creatinine': {'normal': (0, 1.2), 'elevated': (1.2, 10)},
        'Cholesterol': {'desirable': (0, 200), 'borderline': (200, 240), 'high': (240, 500)},
        'LDL': {'optimal': (0, 100), 'borderline': (100, 130), 'high': (130, 500)},
        'HDL': {'low': (0, 40), 'acceptable': (40, 60), 'optimal': (60, 200)},
    }

    def __init__(self):
        """Initialize feature engineer."""
        self.scaler_params = {}

    def extract_age_group(self, age: int) -> Dict[str, int]:
        """
        Convert age to group encoding.
        
        Returns: one-hot encoded age groups
            {
                'age_group_0_17': 0 or 1,
                'age_group_18_34': 0 or 1,
                'age_group_35_49': 0 or 1,
                'age_group_50_64': 0 or 1,
                'age_group_65plus': 0 or 1,
            }
        """
        groups = {
            'age_group_0_17': 1 if 0 <= age <= 17 else 0,
            'age_group_18_34': 1 if 18 <= age <= 34 else 0,
            'age_group_35_49': 1 if 35 <= age <= 49 else 0,
            'age_group_50_64': 1 if 50 <= age <= 64 else 0,
            'age_group_65plus': 1 if age >= 65 else 0,
        }
        return groups

    def encode_gender(self, gender: str) -> Dict[str, int]:
        """
        Encode gender as one-hot.
        
        Returns:
            {'gender_male': 0|1, 'gender_female': 0|1, 'gender_other': 0|1}
        """
        return {
            'gender_male': 1 if gender.lower() == 'male' else 0,
            'gender_female': 1 if gender.lower() == 'female' else 0,
            'gender_other': 1 if gender.lower() not in ['male', 'female'] else 0,
        }

    def encode_blood_group(self, blood_group: str) -> Dict[str, int]:
        """
        Encode blood group as one-hot.
        
        Returns:
            {'blood_group_o': 0|1, 'blood_group_a': 0|1, ...}
        """
        base_type = blood_group[0].lower() if blood_group else 'unknown'
        is_positive = '+' in blood_group if blood_group else False
        
        return {
            'blood_group_o': 1 if base_type == 'o' else 0,
            'blood_group_a': 1 if base_type == 'a' else 0,
            'blood_group_b': 1 if base_type == 'b' else 0,
            'blood_group_ab': 1 if base_type == 'ab' else 0,
            'blood_group_rh_positive': 1 if is_positive else 0,
        }

    def detect_diagnoses(self, diagnoses: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Detect presence of major conditions from ICD-10 codes.
        
        Returns:
            {
                'has_heart_disease': 0|1,
                'has_diabetes': 0|1,
                'has_hypertension': 0|1,
                ...
            }
        """
        detected = {}
        
        for condition, icd_codes in self.CONDITIONS.items():
            found = False
            for diagnosis in diagnoses:
                icd10 = diagnosis.get('icd10_code', '').upper()
                for code in icd_codes:
                    if icd10.startswith(code):
                        found = True
                        break
                if found:
                    break
            detected[f'has_{condition}'] = 1 if found else 0
        
        return detected

    def calculate_comorbidity_index(self, diagnoses: List[Dict[str, Any]]) -> int:
        """
        Calculate Charlson Comorbidity Index (simplified).
        
        Weights conditions by severity and counts them.
        
        Returns: integer comorbidity score (0+)
        """
        weights = {
            'heart_disease': 1,
            'diabetes': 1,
            'hypertension': 1,
            'kidney_disease': 2,
            'copd': 1,
            'cancer': 2,
            'stroke': 2,
        }
        
        score = 0
        detected_conditions = self.detect_diagnoses(diagnoses)
        
        for condition, weight in weights.items():
            if detected_conditions.get(f'has_{condition}', 0):
                score += weight
        
        return score

    def count_chronic_conditions(self, diagnoses: List[Dict[str, Any]]) -> int:
        """
        Count number of chronic diagnoses.
        
        Returns: integer count of chronic conditions
        """
        return sum(1 for d in diagnoses if d.get('is_chronic', False))

    def count_active_medications(self, medications: List[Dict[str, Any]]) -> int:
        """
        Count number of active medications.
        
        Returns: count of dispensed/active prescriptions
        """
        return sum(
            1 for m in medications
            if m.get('dispense_status') != 'cancelled'
        )

    def calculate_medication_complexity(self, medications: List[Dict[str, Any]]) -> float:
        """
        Calculate medication complexity score (polypharmacy indicator).
        
        Score based on:
        - Number of medications
        - Frequency complexity
        - Route diversity
        
        Returns: complexity score 0-100
        """
        if not medications:
            return 0.0
        
        num_meds = self.count_active_medications(medications)
        
        # Frequency weights
        freq_weights = {
            'once daily': 1,
            'twice daily': 2,
            'three times daily': 3,
            'four times daily': 4,
            'as needed': 1,
            'weekly': 1,
            'monthly': 0.5,
        }
        
        freq_score = sum(
            freq_weights.get(m.get('frequency', '').lower(), 2)
            for m in medications
            if m.get('dispense_status') != 'cancelled'
        )
        
        # Route diversity
        unique_routes = len(set(m['route'] for m in medications if m.get('dispense_status') != 'cancelled'))
        
        # Combined score: (meds count * 5) + (frequency score * 2) + (route diversity * 5)
        complexity = min(100, (num_meds * 5) + (freq_score * 2) + (unique_routes * 5))
        
        return complexity

    def calculate_allergy_severity_index(self, allergies: List[Dict[str, Any]]) -> float:
        """
        Calculate overall allergy severity index.
        
        Returns: weighted severity score 0-100
        """
        if not allergies:
            return 0.0
        
        severity_weights = {
            'critical': 100,
            'severe': 50,
            'moderate': 25,
            'mild': 10,
        }
        
        total_severity = 0
        for allergy in allergies:
            severity = allergy.get('severity', 'mild').lower()
            total_severity += severity_weights.get(severity, 10)
        
        # Average severity across allergies
        return min(100, (total_severity / len(allergies)) if allergies else 0)

    def calculate_vital_statistics(self, vitals: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """
        Calculate aggregate vital sign statistics (mean, trend, abnormality).
        
        Returns:
            {
                'bp_systolic_mean': float,
                'bp_diastolic_mean': float,
                'pulse_mean': float,
                'spo2_mean': float,
                'temp_mean': float,
                'weight_mean': float,
                'bmi_mean': float,
                'bp_trend': -1|0|1,  # Declining, stable, increasing
            }
        """
        if not vitals:
            return {
                'bp_systolic_mean': None,
                'bp_diastolic_mean': None,
                'pulse_mean': None,
                'spo2_mean': None,
                'temp_mean': None,
                'weight_mean': None,
                'bmi_mean': None,
                'bp_trend': 0,
            }
        
        # Extract numeric values
        systolic = [v['bp_systolic'] for v in vitals if v.get('bp_systolic')]
        diastolic = [v['bp_diastolic'] for v in vitals if v.get('bp_diastolic')]
        pulse = [v['pulse_bpm'] for v in vitals if v.get('pulse_bpm')]
        spo2 = [v['spo2_percent'] for v in vitals if v.get('spo2_percent')]
        temp = [v['temperature_c'] for v in vitals if v.get('temperature_c')]
        weight = [v['weight_kg'] for v in vitals if v.get('weight_kg')]
        bmi = [v['bmi'] for v in vitals if v.get('bmi')]
        
        # Calculate trend (first vs last for systolic BP)
        bp_trend = 0
        if len(systolic) >= 2:
            if systolic[-1] < systolic[0] - 5:
                bp_trend = -1  # Declining
            elif systolic[-1] > systolic[0] + 5:
                bp_trend = 1   # Increasing
        
        return {
            'bp_systolic_mean': statistics.mean(systolic) if systolic else None,
            'bp_diastolic_mean': statistics.mean(diastolic) if diastolic else None,
            'pulse_mean': statistics.mean(pulse) if pulse else None,
            'spo2_mean': statistics.mean(spo2) if spo2 else None,
            'temp_mean': statistics.mean(temp) if temp else None,
            'weight_mean': statistics.mean(weight) if weight else None,
            'bmi_mean': statistics.mean(bmi) if bmi else None,
            'bp_trend': bp_trend,
        }

    def classify_lab_values(self, labs: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Classify lab values as normal/abnormal based on reference ranges.
        
        Returns:
            {
                'hba1c_status': 'normal'|'prediabetic'|'diabetic'|'unknown',
                'glucose_status': ...,
                'cholesterol_status': ...,
                ...
            }
        """
        classifications = {}
        
        for lab in labs:
            test_name = lab.get('test_name', '').lower()
            result_value_str = lab.get('result_value', '')
            
            # Try to parse result value
            try:
                result_value = float(result_value_str.split()[0]) if result_value_str else None
            except (ValueError, IndexError):
                result_value = None
            
            if not result_value:
                continue
            
            # Match lab test to ranges
            for range_test, ranges in self.LAB_RANGES.items():
                if range_test.lower() in test_name:
                    for status, (low, high) in ranges.items():
                        if low <= result_value <= high:
                            key = f'{range_test.lower().replace(" ", "_")}_status'
                            classifications[key] = status
                            break
        
        return classifications

    def create_feature_vector(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create complete feature vector from raw patient data.
        
        Args:
            patient_data: Output from DataProcessor.extract_complete_patient_data()
        
        Returns:
            Flattened feature dictionary ready for ML models:
            {
                'patient_id': str,
                
                # Demographics
                'age': int,
                'age_group_0_17': int,
                'age_group_18_34': int,
                ...
                'gender_male': int,
                'gender_female': int,
                'blood_group_o': int,
                ...
                
                # Diagnosis-based features
                'has_heart_disease': int,
                'has_diabetes': int,
                ...
                'comorbidity_index': int,
                'chronic_condition_count': int,
                
                # Medication features
                'active_medication_count': int,
                'medication_complexity_score': float,
                
                # Allergy features
                'allergy_count': int,
                'allergy_severity_index': float,
                
                # Vital statistics
                'bp_systolic_mean': float,
                'pulse_mean': float,
                ...
                
                # Lab classifications
                'hba1c_status': str,
                'glucose_status': str,
                ...
                
                # Admission history
                'recent_admission_count': int,
                'avg_los_days': float,

                # Encounter history
                'recent_encounter_count': int,

                # Treatment outcome (derived from most recent completed encounter)
                'treatment_outcome': str or None,
                'outcome_success_rate': float or None,
            }
        """
        try:
            demographics = patient_data['demographics']
            diagnoses = patient_data['diagnoses']
            medications = patient_data['medications']
            allergies = patient_data['allergies']
            vitals = patient_data['vitals']
            labs = patient_data['labs']
            admissions = patient_data['admissions']
            encounters = patient_data['encounters']
            
            features = {
                'patient_id': demographics['patient_id'],
                'age': demographics['age'],
            }
            
            # Age and gender
            features.update(self.extract_age_group(demographics['age']))
            features.update(self.encode_gender(demographics['gender']))
            features.update(self.encode_blood_group(demographics['blood_group']))
            
            # Diagnoses
            features.update(self.detect_diagnoses(diagnoses))
            features['comorbidity_index'] = self.calculate_comorbidity_index(diagnoses)
            features['chronic_condition_count'] = self.count_chronic_conditions(diagnoses)
            
            # Medications
            features['active_medication_count'] = self.count_active_medications(medications)
            features['medication_complexity_score'] = self.calculate_medication_complexity(medications)
            
            # Allergies
            features['allergy_count'] = len(allergies)
            features['allergy_severity_index'] = self.calculate_allergy_severity_index(allergies)
            
            # Vitals
            features.update(self.calculate_vital_statistics(vitals))
            
            # Labs
            features.update(self.classify_lab_values(labs))
            
            # Admission history
            features['recent_admission_count'] = len([a for a in admissions if a['discharged_at'] is None])
            los_vals = [a['length_of_stay_days'] for a in admissions if a.get('length_of_stay_days')]
            if los_vals:
                avg_los = statistics.mean(los_vals)
                features['avg_los_days'] = avg_los if not math.isnan(avg_los) else None
            else:
                features['avg_los_days'] = None
            
            # Encounter history
            features['recent_encounter_count'] = len(encounters)

            # Treatment outcome: derived from encounter status/visit_status in the EMR.
            # An encounter is considered successfully completed when its status is
            # 'completed' or visit_status is 'discharged'.
            _completed = {'completed'}
            _discharged = {'discharged'}
            completed_encounters = [
                e for e in encounters
                if e.get('status') in _completed
                or e.get('visit_status') in _discharged
            ]
            if completed_encounters:
                features['treatment_outcome'] = 'Completed Treatment'
                features['outcome_success_rate'] = (
                    len(completed_encounters) / len(encounters)
                )
            elif encounters:
                features['treatment_outcome'] = 'Treatment Ongoing'
                features['outcome_success_rate'] = 0.0
            else:
                features['treatment_outcome'] = None
                features['outcome_success_rate'] = None

            return features
        
        except Exception as e:
            logger.error(f"Error creating feature vector: {e}")
            raise

    def create_feature_vectors_batch(
        self,
        patient_data_list: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Create feature vectors for multiple patients.
        
        Args:
            patient_data_list: List of patient data from DataProcessor
        
        Returns:
            (feature_dicts, patient_ids)
        """
        features = []
        patient_ids = []
        
        for patient_data in patient_data_list:
            try:
                feature_vector = self.create_feature_vector(patient_data)
                features.append(feature_vector)
                patient_ids.append(feature_vector['patient_id'])
            except Exception as e:
                logger.error(f"Failed to create features for patient: {e}")
                continue
        
        logger.info(f"Created feature vectors for {len(features)} patients")
        return features, patient_ids
