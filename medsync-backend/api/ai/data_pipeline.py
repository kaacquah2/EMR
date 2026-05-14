import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.db import connection
from django.utils import timezone
from api.models import AIAnalysis
from patients.models import Patient, PatientAdmission
from records.models import Vital, Diagnosis

logger = logging.getLogger(__name__)

class PIIDetectedError(Exception):
    """Raised when PII columns are detected in a dataset intended for ML training."""
    pass

class DatasetValidationReport:
    def __init__(self, passed: bool, errors: List[str], warnings: List[str]):
        self.passed = passed
        self.errors = errors
        self.warnings = warnings

    def to_dict(self):
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings
        }

class DataPipeline:
    """
    Handles data extraction, anonymization, and validation for AI model retraining.
    """
    
    PII_COLUMNS = {
        'name', 'full_name', 'phone', 'email', 'address', 
        'national_id', 'ghana_health_id', 'date_of_birth',
        'passport_number', 'nhis_number'
    }

    def load_from_csv(self, filepath: str, target_column: str, feature_columns: List[str]) -> pd.DataFrame:
        """
        Loads and validates a CSV file, ensuring no PII is present.
        """
        df = pd.read_csv(filepath)
        
        # Check for PII in column names
        detected_pii = [col for col in df.columns if col.lower() in self.PII_COLUMNS]
        if detected_pii:
            raise PIIDetectedError(f"PII detected in CSV columns: {detected_pii}")
            
        return df[feature_columns + [target_column]]

    def load_from_database(self, hospital_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> pd.DataFrame:
        """
        Queries the database for anonymized patient features using Django ORM.
        Decryption is handled automatically by the ORM.
        """
        patients = Patient.objects.all()
        if hospital_id:
            patients = patients.filter(registered_at_id=hospital_id)
            
        data = []
        for p in patients:
            # Get latest vitals
            v = Vital.objects.filter(record__patient=p).order_by('-record__created_at').first()
            
            # Get admission count
            adm_count = PatientAdmission.objects.filter(patient=p, admitted_at__gt=timezone.now() - timedelta(days=365)).count()
            
            # Get triage (dummy for now if not linked)
            triage_val = 3 # Default medium
            
            data.append({
                'patient_id': str(p.id),
                'age': (timezone.now().date() - p.date_of_birth).days // 365,
                'gender_encoded': {'male': 0, 'female': 1}.get(p.gender, 2),
                'bp_systolic': float(v.bp_systolic) if v and v.bp_systolic else 120,
                'bp_diastolic': float(v.bp_diastolic) if v and v.bp_diastolic else 80,
                'heart_rate': int(v.pulse_bpm) if v and v.pulse_bpm else 72,
                'temperature': float(v.temperature_c) if v and v.temperature_c else 36.6,
                'spo2': float(v.spo2_percent) if v and v.spo2_percent else 98,
                'respiratory_rate': int(v.resp_rate) if v and v.resp_rate else 16,
                'admission_count_12m': adm_count,
                'readmission_30d': 0 # Target placeholder
            })
            
        df = pd.DataFrame(data)
        logger.info(f"Loaded {len(df)} records from database for retraining")
        return df

    def validate_dataset(self, df: pd.DataFrame, model_type: str) -> DatasetValidationReport:
        """
        Validates dataset completeness and quality.
        """
        errors = []
        warnings = []
        
        # Row count check
        min_rows = 1000 if model_type == 'risk_prediction' else 500
        if len(df) < min_rows:
            errors.append(f"Insufficient data: {len(df)} rows found, minimum {min_rows} required.")
            
        # Missing values check
        missing_pct = df.isnull().mean() * 100
        for col, pct in missing_pct.items():
            if pct > 20:
                errors.append(f"Column '{col}' has {pct:.1f}% missing values (max 20% allowed).")
            elif pct > 5:
                warnings.append(f"Column '{col}' has {pct:.1f}% missing values.")
                
        # Feature completeness (example for risk)
        if model_type == 'risk_prediction':
            expected_features = ['age', 'gender_encoded', 'bp_systolic', 'heart_rate', 'admission_count_12m']
            missing_cols = [col for col in expected_features if col not in df.columns]
            if missing_cols:
                errors.append(f"Missing required features for risk model: {missing_cols}")
                
        passed = len(errors) == 0
        return DatasetValidationReport(passed, errors, warnings)

    def generate_synthetic_data(self, n_samples: int, model_type: str, seed: int = 42) -> pd.DataFrame:
        """
        Generates realistic synthetic data for testing the pipeline.
        """
        np.random.seed(seed)
        
        data = {
            'age': np.random.randint(18, 85, n_samples),
            'gender_encoded': np.random.choice([0, 1], n_samples),
            'bp_systolic': np.random.normal(120, 15, n_samples).astype(int),
            'bp_diastolic': np.random.normal(80, 10, n_samples).astype(int),
            'heart_rate': np.random.normal(72, 10, n_samples).astype(int),
            'temperature': np.random.normal(36.6, 0.5, n_samples),
            'spo2': np.random.normal(98, 2, n_samples),
            'respiratory_rate': np.random.normal(16, 3, n_samples).astype(int),
            'admission_count_12m': np.random.poisson(0.5, n_samples),
            'synthetic_data': True
        }
        
        if model_type == 'risk_prediction':
            # Target: readmission_30d
            # Simple logic: higher age and systolic BP increase risk
            risk_prob = 1 / (1 + np.exp(-(0.05 * data['age'] + 0.01 * data['bp_systolic'] - 5)))
            data['readmission_30d'] = (np.random.random(n_samples) < risk_prob).astype(int)
        else:
            # Target: triage_level (1-5)
            data['esi_level'] = np.random.choice([1, 2, 3, 4, 5], n_samples, p=[0.05, 0.15, 0.4, 0.3, 0.1])
            
        df = pd.DataFrame(data)
        setattr(df, 'synthetic_data', True)
        
        logger.info(f"Generated {n_samples} synthetic records for {model_type}")
        return df
