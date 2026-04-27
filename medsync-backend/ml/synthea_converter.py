"""
synthea_converter.py
Convert Synthea CSV output to MedSync ML training format
Ghana-calibrated synthetic patient data
"""

import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import json


class SyntheaToMedSyncConverter:
    """
    Converts Synthea CSV output into the feature format expected by MedSync's ML pipeline.
    Handles Ghana-specific disease codes and configurations.
    """

    # LOINC codes for vital signs
    LOINC_CODES = {
        'systolic_bp': '8480-6',
        'diastolic_bp': '8462-4',
        'heart_rate': '8867-4',
        'temperature': '8310-5',
        'spo2': '2708-6',
        'respiratory_rate': '9279-1',
        'haemoglobin': '718-7',
        'wbc_count': '6690-2',
        'blood_glucose': '2339-0',
        'creatinine': '2160-0',
    }

    # SNOMED-CT codes for Ghana-specific diseases
    SNOMED_CONDITIONS = {
        'malaria': '61462000',
        'sickle_cell': '127040003',
        'diabetes': '44054006',
        'hypertension': '38341003',
        'hiv': '86406008',
        'tuberculosis': '56717001',
        'copd': '13645005',
        'pneumonia': '233604007',
    }

    def __init__(self, synthea_output_dir: str, output_file: Optional[str] = None):
        """
        Initialize converter with Synthea output directory.
        
        Args:
            synthea_output_dir: Path to Synthea output directory (contains CSV files)
            output_file: Optional output CSV filename (default: medsync_training_data.csv)
        """
        self.dir = Path(synthea_output_dir)
        self.output_file = output_file or 'medsync_training_data.csv'
        
        # Validate directory exists
        if not self.dir.exists():
            raise ValueError(f"Synthea output directory not found: {self.dir}")
    
    def convert(self) -> pd.DataFrame:
        """
        Convert Synthea CSV files to MedSync ML format.
        
        Returns:
            DataFrame with MedSync training features
        """
        print(f"Loading Synthea data from {self.dir}...")
        
        # Load CSV files
        try:
            patients = pd.read_csv(self.dir / 'patients.csv')
            conditions = pd.read_csv(self.dir / 'conditions.csv')
            observations = pd.read_csv(self.dir / 'observations.csv')
            medications = pd.read_csv(self.dir / 'medications.csv')
            encounters = pd.read_csv(self.dir / 'encounters.csv')
        except FileNotFoundError as e:
            print(f"Error: Could not load Synthea CSV files: {e}")
            sys.exit(1)
        
        print(f"Loaded {len(patients)} patients, {len(encounters)} encounters")
        
        records = []
        for idx, (_, patient) in enumerate(patients.iterrows()):
            if idx % 100 == 0:
                print(f"  Processing patient {idx}/{len(patients)}")
            
            try:
                pid = patient['Id']
                
                # Get patient's records
                pt_conditions = conditions[conditions['PATIENT'] == pid]
                pt_obs = observations[observations['PATIENT'] == pid]
                pt_medications = medications[medications['PATIENT'] == pid]
                pt_encounters = encounters[encounters['PATIENT'] == pid]
                
                # Build feature vector
                record = {
                    'patient_id': pid,
                    'age_group': self._age_bucket(patient['BIRTHDATE']),
                    'gender': patient['GENDER'].lower() if pd.notna(patient['GENDER']) else 'unknown',
                    
                    # Vitals from observations
                    'systolic_bp': self._obs_val(pt_obs, self.LOINC_CODES['systolic_bp']),
                    'diastolic_bp': self._obs_val(pt_obs, self.LOINC_CODES['diastolic_bp']),
                    'heart_rate': self._obs_val(pt_obs, self.LOINC_CODES['heart_rate']),
                    'temperature': self._obs_val(pt_obs, self.LOINC_CODES['temperature']),
                    'spo2': self._obs_val(pt_obs, self.LOINC_CODES['spo2']),
                    'respiratory_rate': self._obs_val(pt_obs, self.LOINC_CODES['respiratory_rate']),
                    
                    # Labs
                    'haemoglobin': self._obs_val(pt_obs, self.LOINC_CODES['haemoglobin']),
                    'wbc_count': self._obs_val(pt_obs, self.LOINC_CODES['wbc_count']),
                    'blood_glucose': self._obs_val(pt_obs, self.LOINC_CODES['blood_glucose']),
                    'creatinine': self._obs_val(pt_obs, self.LOINC_CODES['creatinine']),
                    
                    # Ghana-specific disease flags
                    'has_malaria': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['malaria']),
                    'has_sickle_cell': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['sickle_cell']),
                    'has_diabetes': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['diabetes']),
                    'has_hypertension': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['hypertension']),
                    'has_hiv': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['hiv']),
                    'has_tuberculosis': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['tuberculosis']),
                    'has_copd': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['copd']),
                    'has_pneumonia': self._has_condition(pt_conditions, self.SNOMED_CONDITIONS['pneumonia']),
                    
                    # Utilization metrics
                    'num_encounters_6m': len(pt_encounters[
                        pd.to_datetime(pt_encounters['START'], errors='coerce') > 
                        datetime.now() - timedelta(days=180)
                    ]) if len(pt_encounters) > 0 else 0,
                    'num_medications': len(pt_medications),
                    'num_conditions': len(pt_conditions),
                    
                    # Emergency visit indicator
                    'had_emergency_visit': int(
                        'emergency' in pt_encounters['ENCOUNTERCLASS'].values.astype(str).lower()
                    ) if len(pt_encounters) > 0 else 0,
                    
                    # Target (simulated readmission risk)
                    'readmitted_30d': self._simulate_readmission(pt_encounters),
                    
                    # Metadata
                    'record_date': datetime.now().isoformat(),
                }
                
                records.append(record)
            except Exception as e:
                print(f"  Warning: Error processing patient {pid}: {e}")
                continue
        
        df = pd.DataFrame(records)
        print(f"Converted {len(df)} patient records")
        return df
    
    def _obs_val(self, obs_df: pd.DataFrame, loinc_code: str) -> Optional[float]:
        """Extract numeric observation value by LOINC code."""
        if obs_df.empty:
            return None
        
        row = obs_df[obs_df['CODE'] == loinc_code]
        if row.empty:
            return None
        
        try:
            value = row.iloc[0]['VALUE']
            return float(value) if pd.notna(value) else None
        except (ValueError, TypeError):
            return None
    
    def _has_condition(self, cond_df: pd.DataFrame, snomed_code: str) -> int:
        """Check if patient has a condition by SNOMED-CT code."""
        if cond_df.empty:
            return 0
        return int(snomed_code in cond_df['CODE'].values)
    
    def _age_bucket(self, birthdate: str) -> str:
        """Bucket age into standard groups."""
        try:
            dob = pd.to_datetime(birthdate).date()
            age = (datetime.now().date() - dob).days // 365
            
            if age < 0:
                return '0-1'
            elif age < 5:
                return '<5'
            elif age < 18:
                return '5-18'
            elif age < 40:
                return '18-40'
            elif age < 65:
                return '40-65'
            else:
                return '65+'
        except Exception:
            return 'unknown'
    
    def _simulate_readmission(self, encounters_df: pd.DataFrame) -> int:
        """
        Simulate 30-day readmission risk based on encounter patterns.
        Proxy: >2 ED visits or hospitalization = readmission risk.
        """
        if encounters_df.empty:
            return 0
        
        # Recent encounters (last 60 days)
        recent_cutoff = datetime.now() - timedelta(days=60)
        try:
            recent = encounters_df[
                pd.to_datetime(encounters_df['START'], errors='coerce') > recent_cutoff
            ]
        except Exception:
            recent = encounters_df
        
        if len(recent) == 0:
            return 0
        
        # Count emergency visits
        encounter_class = recent['ENCOUNTERCLASS'].astype(str).str.lower()
        ed_visits = (encounter_class == 'emergency').sum()
        inpatient = (encounter_class == 'inpatient').sum()
        
        # Readmission proxy: ED visits >= 2 or recent inpatient stay
        return int(ed_visits >= 2 or inpatient >= 1)
    
    def save(self, df: pd.DataFrame, output_path: Optional[str] = None) -> str:
        """
        Save converted data to CSV.
        
        Args:
            df: DataFrame to save
            output_path: Optional output path (default: self.output_file)
        
        Returns:
            Path to saved file
        """
        path = output_path or self.output_file
        
        print(f"\nSaving {len(df)} records to {path}...")
        df.to_csv(path, index=False)
        
        # Print summary statistics
        print("\n=== Conversion Summary ===")
        print(f"Total records: {len(df)}")
        print(f"\nDisease prevalence:")
        print(f"  Malaria: {df['has_malaria'].sum()} ({100*df['has_malaria'].mean():.2f}%)")
        print(f"  Sickle cell: {df['has_sickle_cell'].sum()} ({100*df['has_sickle_cell'].mean():.2f}%)")
        print(f"  Diabetes: {df['has_diabetes'].sum()} ({100*df['has_diabetes'].mean():.2f}%)")
        print(f"  Hypertension: {df['has_hypertension'].sum()} ({100*df['has_hypertension'].mean():.2f}%)")
        print(f"  HIV: {df['has_hiv'].sum()} ({100*df['has_hiv'].mean():.2f}%)")
        print(f"\nReadmission risk: {df['readmitted_30d'].sum()} ({100*df['readmitted_30d'].mean():.2f}%)")
        print(f"Emergency visits: {df['had_emergency_visit'].sum()} ({100*df['had_emergency_visit'].mean():.2f}%)")
        
        return path


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert Synthea CSV output to MedSync ML training format'
    )
    parser.add_argument(
        'synthea_dir',
        help='Path to Synthea CSV output directory'
    )
    parser.add_argument(
        '-o', '--output',
        default='medsync_training_data.csv',
        help='Output CSV filename (default: medsync_training_data.csv)'
    )
    
    args = parser.parse_args()
    
    try:
        converter = SyntheaToMedSyncConverter(args.synthea_dir, args.output)
        df = converter.convert()
        converter.save(df)
        print(f"\n✓ Conversion complete! Output: {args.output}")
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
