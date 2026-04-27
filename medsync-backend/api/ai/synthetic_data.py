"""
Generate Ghana-specific synthetic patient data for MedSync AI model training.

This module creates realistic patient data with Ghana-appropriate disease prevalence rates.
Used for developing and testing ML models before deployment with real patient data.

Ghana Epidemiology (Sources: Ghana Health Service, CDC):
- Malaria: 25% annual incidence (endemic in most regions)
- Sickle cell disease: 2% of population (high in Northern regions)
- Hypertension: 18-20% of adults
- Diabetes: 4-5% of adults
- HIV: 1.5% of population (~400,000 people)
- Tuberculosis: 70-100 cases per 100,000/year

Data Features (26-dimensional after feature engineering):
- Demographics: age, gender
- Vitals: systolic_bp, diastolic_bp, heart_rate, temperature, spo2, respiratory_rate
- Labs: hemoglobin, wbc_count, blood_glucose, creatinine
- Conditions: malaria, sickle_cell, diabetes, hypertension, hiv
- Encounter history: num_encounters_6m

Target Variable:
- readmitted_30d: Binary (1=readmitted within 30 days, 0=discharged successfully)
  Simulated based on clinical risk factors (vitals, conditions, demographics)

Example Usage:
    from api.ai.synthetic_data import generate_ghana_synthetic_cohort
    
    df = generate_ghana_synthetic_cohort(n_samples=500)
    print(f"Generated {len(df)} patients")
    print(f"Readmission rate: {df['readmitted_30d'].mean():.1%}")
    print(f"Malaria prevalence: {df['has_malaria'].mean():.1%}")
"""

import logging
from typing import Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def generate_ghana_synthetic_cohort(n_samples: int = 500, seed: int = 42) -> pd.DataFrame:
    """
    Generate realistic Ghana-specific synthetic patient data.
    
    Args:
        n_samples: Number of patients to generate (default: 500)
        seed: Random seed for reproducibility (default: 42)
    
    Returns:
        pd.DataFrame with columns:
            - patient_id, age, gender
            - systolic_bp, diastolic_bp, heart_rate, temperature, spo2, respiratory_rate
            - hemoglobin, wbc_count, blood_glucose, creatinine
            - has_malaria, has_sickle_cell, has_diabetes, has_hypertension, has_hiv
            - num_encounters_6m, readmitted_30d (target)
    """
    np.random.seed(seed)
    logger.info(f"Generating {n_samples} synthetic Ghana patients...")
    
    # Demographics (age distribution: Ghana has young population, median ~21 years)
    ages = np.random.normal(loc=45, scale=18, size=n_samples).clip(18, 95).astype(int)
    genders = np.random.choice(['M', 'F'], n_samples, p=[0.48, 0.52])
    
    # Vitals (realistic for health facility visits)
    systolic_bp = np.random.normal(120, 15, n_samples).clip(80, 200)
    diastolic_bp = np.random.normal(80, 10, n_samples).clip(50, 130)
    heart_rate = np.random.normal(75, 15, n_samples).clip(40, 140)
    temperature = np.random.normal(37.0, 0.5, n_samples).clip(35, 40)
    spo2 = np.random.normal(97, 2, n_samples).clip(85, 100)
    respiratory_rate = np.random.normal(16, 3, n_samples).clip(8, 35)
    
    # Labs
    hemoglobin = np.random.normal(13, 2, n_samples).clip(6, 18)  # g/dL
    wbc_count = np.random.normal(7.5, 2, n_samples).clip(2, 15)  # K/uL
    blood_glucose = np.random.normal(100, 30, n_samples).clip(50, 300)  # mg/dL
    creatinine = np.random.normal(1.0, 0.3, n_samples).clip(0.5, 3.0)  # mg/dL
    
    # Ghana disease prevalence
    has_malaria = np.random.binomial(1, 0.25, n_samples)  # 25% annual incidence
    has_sickle_cell = np.random.binomial(1, 0.02, n_samples)  # 2% of population
    has_diabetes = np.random.binomial(1, 0.045, n_samples)  # 4-5% of adults
    has_hypertension = np.random.binomial(1, 0.19, n_samples)  # 18-20% of adults
    has_hiv = np.random.binomial(1, 0.015, n_samples)  # 1.5% of population
    
    # Encounter history
    num_encounters_6m = np.random.randint(0, 12, n_samples)  # 0-11 visits in past 6 months
    
    # Construct DataFrame
    df = pd.DataFrame({
        'patient_id': range(n_samples),
        'age': ages,
        'gender': genders,
        'systolic_bp': systolic_bp,
        'diastolic_bp': diastolic_bp,
        'heart_rate': heart_rate,
        'temperature': temperature,
        'spo2': spo2,
        'respiratory_rate': respiratory_rate,
        'hemoglobin': hemoglobin,
        'wbc_count': wbc_count,
        'blood_glucose': blood_glucose,
        'creatinine': creatinine,
        'has_malaria': has_malaria,
        'has_sickle_cell': has_sickle_cell,
        'has_diabetes': has_diabetes,
        'has_hypertension': has_hypertension,
        'has_hiv': has_hiv,
        'num_encounters_6m': num_encounters_6m,
    })
    
    # Simulate 30-day readmission based on clinical risk factors
    risk_score = _calculate_readmission_risk(df)
    df['readmitted_30d'] = (risk_score > np.random.uniform(0, 1, n_samples)).astype(int)
    
    logger.info(f"Generated {len(df)} synthetic patients. "
                f"Readmission rate: {df['readmitted_30d'].mean():.1%}")
    logger.debug(f"Malaria prevalence: {df['has_malaria'].mean():.1%} | "
                 f"Sickle cell: {df['has_sickle_cell'].mean():.1%} | "
                 f"Hypertension: {df['has_hypertension'].mean():.1%}")
    
    return df


def _calculate_readmission_risk(df: pd.DataFrame) -> np.ndarray:
    """
    Calculate 30-day readmission risk based on clinical factors.
    
    Risk factors (weights):
    - Elevated BP (>140 systolic): 20%
    - Elevated glucose (>150 mg/dL): 20%
    - Diabetes: 15%
    - Hypertension: 15%
    - Age >65: 15%
    - Malaria: 10%
    - Elevated WBC (>10 K/uL): 5%
    
    Args:
        df: Patient DataFrame
    
    Returns:
        np.ndarray of risk scores (0-1)
    """
    risk_score = (
        (df['systolic_bp'] > 140).astype(int) * 0.20 +
        (df['blood_glucose'] > 150).astype(int) * 0.20 +
        (df['has_diabetes'] == 1).astype(int) * 0.15 +
        (df['has_hypertension'] == 1).astype(int) * 0.15 +
        (df['age'] > 65).astype(int) * 0.15 +
        (df['has_malaria'] == 1).astype(int) * 0.10 +
        (df['wbc_count'] > 10).astype(int) * 0.05
    )
    return risk_score


class GhanaSyntheticCohort:
    """
    Factory class for generating Ghana-specific synthetic cohorts.
    
    Supports stratified sampling by disease or age group for controlled experiments.
    """
    
    @staticmethod
    def generate_by_disease(disease: str, n_samples: int = 100, seed: int = 42) -> pd.DataFrame:
        """
        Generate patients with a specific disease condition.
        
        Args:
            disease: 'malaria', 'diabetes', 'hypertension', 'hiv', or 'sickle_cell'
            n_samples: Number of patients (will be oversampled for disease prevalence)
            seed: Random seed
        
        Returns:
            pd.DataFrame with all patients having the specified disease
        """
        # Generate more samples to ensure we get enough with the disease
        df_base = generate_ghana_synthetic_cohort(n_samples=n_samples * 5, seed=seed)
        
        disease_map = {
            'malaria': 'has_malaria',
            'diabetes': 'has_diabetes',
            'hypertension': 'has_hypertension',
            'hiv': 'has_hiv',
            'sickle_cell': 'has_sickle_cell',
        }
        
        if disease not in disease_map:
            raise ValueError(f"Unknown disease: {disease}. Choose from: {list(disease_map.keys())}")
        
        col = disease_map[disease]
        df_disease = df_base[df_base[col] == 1].head(n_samples)
        
        if len(df_disease) < n_samples:
            logger.warning(f"Could not generate {n_samples} patients with {disease}. "
                          f"Generated {len(df_disease)} instead.")
        
        return df_disease.reset_index(drop=True)
    
    @staticmethod
    def generate_by_age_group(age_min: int = 65, age_max: int = 95, 
                             n_samples: int = 100, seed: int = 42) -> pd.DataFrame:
        """
        Generate patients within an age range (e.g., elderly, pediatric).
        
        Args:
            age_min: Minimum age (default: 65, for elderly cohort)
            age_max: Maximum age (default: 95)
            n_samples: Number of patients
            seed: Random seed
        
        Returns:
            pd.DataFrame with all patients in the specified age range
        """
        df_base = generate_ghana_synthetic_cohort(n_samples=n_samples * 3, seed=seed)
        df_age = df_base[(df_base['age'] >= age_min) & (df_base['age'] <= age_max)].head(n_samples)
        
        if len(df_age) < n_samples:
            logger.warning(f"Could not generate {n_samples} patients aged {age_min}-{age_max}. "
                          f"Generated {len(df_age)} instead.")
        
        return df_age.reset_index(drop=True)


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("GHANA SYNTHETIC DATA GENERATION - EXAMPLES")
    print("=" * 70)
    
    # General cohort
    df = generate_ghana_synthetic_cohort(n_samples=100)
    print(f"\n✓ Generated {len(df)} general patients")
    print(f"  - Readmission rate: {df['readmitted_30d'].mean():.1%}")
    print(f"  - Age range: {df['age'].min()}-{df['age'].max()} years")
    print(f"  - Malaria: {df['has_malaria'].mean():.1%} | Diabetes: {df['has_diabetes'].mean():.1%}")
    
    # Elderly cohort
    df_elderly = GhanaSyntheticCohort.generate_by_age_group(age_min=65, n_samples=50)
    print(f"\n✓ Generated {len(df_elderly)} elderly patients (65+)")
    print(f"  - Readmission rate: {df_elderly['readmitted_30d'].mean():.1%}")
    print(f"  - Mean age: {df_elderly['age'].mean():.1f} years")
    
    # Malaria cohort
    df_malaria = GhanaSyntheticCohort.generate_by_disease(disease='malaria', n_samples=50)
    print(f"\n✓ Generated {len(df_malaria)} patients with malaria")
    print(f"  - Readmission rate: {df_malaria['readmitted_30d'].mean():.1%}")
    print(f"  - Mean hemoglobin: {df_malaria['hemoglobin'].mean():.1f} g/dL")
