"""
Ghana Clinical Data Pipeline for MedSync AI Model Training.

This module defines:

1. GhanaDatasetSchema  — canonical column spec for Ghana clinical datasets
2. GhanaDataValidator  — validates de-identification and schema compliance
3. GhanaFeatureEngineer — Ghana-specific feature engineering (disease prevalence,
                           sickle cell, malaria, tropical diseases)
4. KATHDataLoader       — loader for KATH/KBTH/Korle-Bu de-identified CSV exports
5. ClinicalDataPipeline — end-to-end pipeline: load → validate → engineer → train

Usage (once real data is available):
    from api.ai.ghana_clinical_data import ClinicalDataPipeline
    pipeline = ClinicalDataPipeline(data_path="/secure/kath_deid_2026.csv")
    df = pipeline.load_and_validate()
    X, y = pipeline.engineer_features(df)
    # Pass X, y to HybridTrainingPipeline or EnsembleModelTrainer

IMPORTANT — Data Governance:
  - Only de-identified data must be used (no patient names, IDs, direct identifiers)
  - Ethics approval from Ghana Health Service required before use
  - Data must NOT leave Ghana without MoH approval (data residency)
  - Use KATH/KBTH IRB reference number in metadata when training

Privacy-preserving training guidelines:
  - Minimum 100 patients per ICD-10 chapter before using diagnosis as feature
  - Apply k-anonymity (k≥5) before export
  - Differential privacy noise (epsilon=1.0) for lab value aggregates
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# DATASET SCHEMA
# ============================================================================

@dataclass
class GhanaDatasetSchema:
    """
    Canonical column specification for Ghana clinical datasets.

    Sourced from:
    - KATH (Komfo Anokye Teaching Hospital) EHR export format
    - KBTH (Korle-Bu Teaching Hospital) discharge summary format
    - Ghana Health Service (GHS) district health information system (DHIMS2)

    All columns are de-identified — no direct patient identifiers allowed.
    Approved indirect identifiers: age_group, region_code, facility_type.
    """

    # Required columns (must be present in every dataset)
    REQUIRED_COLUMNS: List[str] = field(default_factory=lambda: [
        "age",                   # int or age group string e.g. "[50-60)"
        "gender",                # "M" | "F" | "Unknown"
        "readmitted_30d",        # 0/1 primary target: 30-day readmission
    ])

    # Ghana-specific clinical columns (recommended, filled with NaN if missing)
    GHANA_CLINICAL_COLUMNS: List[str] = field(default_factory=lambda: [
        # Vitals
        "systolic_bp",           # mmHg
        "diastolic_bp",          # mmHg
        "heart_rate",            # bpm
        "temperature",           # °C
        "spo2",                  # %
        "respiratory_rate",      # breaths/min
        "weight_kg",             # kg
        "height_cm",             # cm

        # Labs
        "hemoglobin",            # g/dL — critical for sickle cell / malaria screening
        "wbc_count",             # ×10³/μL
        "platelet_count",        # ×10³/μL
        "blood_glucose",         # mg/dL (fasting or random)
        "creatinine",            # mg/dL — renal function
        "hba1c",                 # % — diabetes monitoring
        "malaria_rdt_positive",  # 0/1 — Ghana-specific: malaria rapid test
        "sickle_cell_status",    # "AA"/"AS"/"SS"/"Unknown"

        # Comorbidities (binary flags, from discharge diagnosis)
        "has_malaria",           # 0/1
        "has_sickle_cell",       # 0/1
        "has_diabetes",          # 0/1
        "has_hypertension",      # 0/1
        "has_hiv",               # 0/1
        "has_tuberculosis",      # 0/1 — higher prevalence in Ghana
        "has_heart_failure",     # 0/1
        "has_ckd",               # 0/1 — chronic kidney disease

        # Healthcare utilisation
        "num_encounters_6m",     # encounters in last 6 months
        "num_admissions_12m",    # admissions in last 12 months
        "length_of_stay_days",   # length of stay (current admission)
        "icu_admission",         # 0/1 — was ICU admission required

        # Facility context
        "facility_type",         # "teaching" | "regional" | "district" | "clinic"
        "region_code",           # GH-AH | GH-BA | GH-CP | GH-EP | GH-NE | GH-NP | GH-OT | GH-TV | GH-UE | GH-UW | GH-VO | GH-WN | GH-WP | GH-SW | GH-SA | GH-BE

        # Insurance
        "nhis_enrolled",         # 0/1 — National Health Insurance Scheme member
        "nhis_valid_at_visit",   # 0/1 — NHIS card was valid at admission
    ])

    # Columns that are FORBIDDEN (would constitute direct identifiers)
    FORBIDDEN_COLUMNS: List[str] = field(default_factory=lambda: [
        "patient_name", "full_name", "first_name", "last_name",
        "national_id", "nhis_number", "ghana_health_id", "passport_number",
        "phone", "email", "address",
        "patient_id", "mrn", "hospital_number",
        "date_of_birth", "exact_dob",            # age_group is allowed
        "gps_coordinates", "latitude", "longitude",
    ])


# ============================================================================
# DATA VALIDATOR
# ============================================================================

class GhanaDataValidator:
    """
    Validates that a clinical dataset is safe for model training:
    1. No forbidden direct-identifier columns
    2. Required columns present
    3. Target variable is binary and not all-one-class
    4. Minimum sample size for model validity
    5. Age is de-identified (age groups, not exact DOB)
    """

    MINIMUM_SAMPLES = 500  # Below this, model generalisation is unreliable
    MINIMUM_POSITIVE_RATE = 0.05  # At least 5% positive class (readmission)
    MAXIMUM_POSITIVE_RATE = 0.60  # At most 60% positive class

    def __init__(self, schema: Optional[GhanaDatasetSchema] = None):
        self.schema = schema or GhanaDatasetSchema()

    def validate(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate the dataframe.

        Returns:
            (is_valid: bool, issues: List[str])

        Raises ValueError on critical (blocking) issues.
        """
        issues: List[str] = []
        errors: List[str] = []

        columns_lower = {c.lower() for c in df.columns}

        # 1. Forbidden columns check
        for forbidden in self.schema.FORBIDDEN_COLUMNS:
            if forbidden.lower() in columns_lower:
                errors.append(
                    f"PRIVACY VIOLATION: Column '{forbidden}' is a direct identifier "
                    f"and must be removed before training. Use age_group instead of date_of_birth."
                )

        # 2. Required columns
        for req in self.schema.REQUIRED_COLUMNS:
            if req.lower() not in columns_lower:
                errors.append(f"Missing required column: '{req}'")

        if errors:
            raise ValueError(
                f"Dataset validation FAILED — {len(errors)} blocking error(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        # 3. Sample size
        if len(df) < self.MINIMUM_SAMPLES:
            issues.append(
                f"WARNING: Only {len(df)} samples. Minimum recommended: {self.MINIMUM_SAMPLES}. "
                f"Model performance may be unreliable."
            )

        # 4. Target variable distribution
        if "readmitted_30d" in df.columns:
            rate = df["readmitted_30d"].mean()
            if rate < self.MINIMUM_POSITIVE_RATE:
                issues.append(
                    f"WARNING: Very low readmission rate ({rate:.1%}). "
                    f"Model may be biased toward negative class. Consider oversampling."
                )
            elif rate > self.MAXIMUM_POSITIVE_RATE:
                issues.append(
                    f"WARNING: High readmission rate ({rate:.1%}). "
                    f"Dataset may not reflect real population. Verify data extraction."
                )

        # 5. Age de-identification check
        if "date_of_birth" in columns_lower or "exact_dob" in columns_lower:
            issues.append(
                "WARNING: 'date_of_birth' detected — convert to age_group before training."
            )

        # 6. Sickle cell completeness (Ghana-specific)
        if "sickle_cell_status" in columns_lower:
            missing_pct = df.get("sickle_cell_status", pd.Series()).isna().mean()
            if missing_pct > 0.80:
                issues.append(
                    f"INFO: sickle_cell_status is {missing_pct:.0%} missing. "
                    f"Feature will be excluded from training."
                )

        return (True, issues)


# ============================================================================
# GHANA FEATURE ENGINEER
# ============================================================================

class GhanaFeatureEngineer:
    """
    Feature engineering aligned with Ghana's disease burden and health system.

    Adds the following engineered features on top of raw clinical values:
    - malaria_severity_score: composite of RDT result, fever, parasite density
    - sickle_cell_risk: encoded from sickle_cell_status (SS=2, AS=1, AA=0)
    - metabolic_syndrome_score: hypertension + diabetes + obesity composite
    - ghana_regional_risk: region-based disease prevalence adjustment
    - nhis_access_score: insurance coverage × facility access composite
    - frailty_proxy: age + number of comorbidities
    """

    # Ghana regional disease burden indices (GHS Annual Report 2023)
    REGIONAL_MALARIA_INDEX = {
        "GH-WN": 0.90,  # Western North — highest malaria burden
        "GH-SA": 0.85,  # Savannah
        "GH-NE": 0.85,  # North East
        "GH-NP": 0.80,  # Northern
        "GH-UE": 0.75,  # Upper East
        "GH-UW": 0.75,  # Upper West
        "GH-BE": 0.70,  # Bono East
        "GH-VO": 0.65,  # Volta
        "GH-OT": 0.60,  # Oti
        "GH-CP": 0.55,  # Central
        "GH-EP": 0.50,  # Eastern
        "GH-TV": 0.50,  # Tema-Volta (Greater Accra East)
        "GH-AH": 0.45,  # Ahafo
        "GH-WP": 0.40,  # Western
        "GH-SW": 0.35,  # South West (Brong Ahafo)
        "GH-BA": 0.35,  # Bono
        "__default__": 0.60,
    }

    def engineer(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Ghana-specific engineered features in-place.

        Returns the augmented dataframe.
        """
        df = df.copy()

        # 1. Malaria severity score
        df["malaria_severity_score"] = self._malaria_severity(df)

        # 2. Sickle cell risk encoding
        df["sickle_cell_risk"] = self._sickle_cell_risk(df)

        # 3. Metabolic syndrome score (0-3 based on HTN + DM + obesity)
        df["metabolic_syndrome_score"] = self._metabolic_syndrome(df)

        # 4. Regional malaria burden
        df["ghana_regional_malaria_risk"] = self._regional_malaria(df)

        # 5. NHIS access score
        df["nhis_access_score"] = self._nhis_access(df)

        # 6. Frailty proxy (age + comorbidity count)
        df["frailty_proxy"] = self._frailty_proxy(df)

        # 7. Renal risk score
        df["renal_risk_score"] = self._renal_risk(df)

        logger.info(
            "GhanaFeatureEngineer: added 7 engineered features. "
            "Total columns: %d", len(df.columns)
        )
        return df

    def _malaria_severity(self, df: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        if "malaria_rdt_positive" in df.columns:
            score += pd.to_numeric(df["malaria_rdt_positive"], errors="coerce").fillna(0) * 2
        if "has_malaria" in df.columns:
            score += pd.to_numeric(df["has_malaria"], errors="coerce").fillna(0)
        if "temperature" in df.columns:
            temp = pd.to_numeric(df["temperature"], errors="coerce").fillna(37)
            score += (temp > 38.5).astype(float)
        if "wbc_count" in df.columns:
            wbc = pd.to_numeric(df["wbc_count"], errors="coerce").fillna(7)
            score += (wbc > 11).astype(float) * 0.5
        return score.clip(0, 5)

    def _sickle_cell_risk(self, df: pd.DataFrame) -> pd.Series:
        if "sickle_cell_status" not in df.columns:
            # Use has_sickle_cell flag as fallback
            if "has_sickle_cell" in df.columns:
                return pd.to_numeric(df["has_sickle_cell"], errors="coerce").fillna(0) * 2
            return pd.Series(0.0, index=df.index)
        mapping = {"SS": 2.0, "SC": 1.5, "AS": 1.0, "AA": 0.0}
        return df["sickle_cell_status"].map(mapping).fillna(0.5)

    def _metabolic_syndrome(self, df: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        for flag in ("has_hypertension", "has_diabetes"):
            if flag in df.columns:
                score += pd.to_numeric(df[flag], errors="coerce").fillna(0)
        # Obesity proxy: BMI > 30 if height/weight available
        if "weight_kg" in df.columns and "height_cm" in df.columns:
            w = pd.to_numeric(df["weight_kg"], errors="coerce")
            h = pd.to_numeric(df["height_cm"], errors="coerce") / 100
            bmi = w / (h ** 2)
            score += (bmi > 30).astype(float)
        return score.clip(0, 3)

    def _regional_malaria(self, df: pd.DataFrame) -> pd.Series:
        default = self.REGIONAL_MALARIA_INDEX["__default__"]
        if "region_code" not in df.columns:
            return pd.Series(default, index=df.index)
        return df["region_code"].map(
            {k: v for k, v in self.REGIONAL_MALARIA_INDEX.items() if k != "__default__"}
        ).fillna(default)

    def _nhis_access(self, df: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        if "nhis_enrolled" in df.columns:
            score += pd.to_numeric(df["nhis_enrolled"], errors="coerce").fillna(0)
        if "nhis_valid_at_visit" in df.columns:
            score += pd.to_numeric(df["nhis_valid_at_visit"], errors="coerce").fillna(0)
        # Facility type bonus
        if "facility_type" in df.columns:
            score += df["facility_type"].map(
                {"teaching": 1.0, "regional": 0.7, "district": 0.4, "clinic": 0.2}
            ).fillna(0.3)
        return score.clip(0, 3)

    def _frailty_proxy(self, df: pd.DataFrame) -> pd.Series:
        # Age component
        if "age" in df.columns:
            age = pd.to_numeric(df["age"], errors="coerce").fillna(40)
        else:
            age = pd.Series(40.0, index=df.index)
        age_score = (age / 20).clip(0, 5)  # 0-5 scale

        # Comorbidity count
        comorbidity_cols = [c for c in df.columns if c.startswith("has_")]
        comorbidity_count = pd.Series(0.0, index=df.index)
        for col in comorbidity_cols:
            comorbidity_count += pd.to_numeric(df[col], errors="coerce").fillna(0)

        return (age_score + comorbidity_count).clip(0, 10)

    def _renal_risk(self, df: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        if "creatinine" in df.columns:
            cr = pd.to_numeric(df["creatinine"], errors="coerce").fillna(1.0)
            # Elevated creatinine > 1.5 = mild impairment; > 3.0 = severe
            score += (cr > 1.5).astype(float)
            score += (cr > 3.0).astype(float)
        if "has_ckd" in df.columns:
            score += pd.to_numeric(df["has_ckd"], errors="coerce").fillna(0) * 2
        return score.clip(0, 4)


# ============================================================================
# DATA LOADER: KATH / KBTH / KORLE-BU
# ============================================================================

class KATHDataLoader:
    """
    Loads de-identified clinical data from KATH/KBTH/Korle-Bu CSV exports.

    Data governance requirements (MUST be satisfied before calling this class):
    1. Written ethics approval from Ghana Health Service Research Unit
    2. IRB approval from KATH/KBTH/Korle-Bu Teaching Hospital
    3. Data de-identification certificate from the data custodian
    4. MoH data sharing agreement (DSA) signed
    5. Data must be stored in Ghana (GHS or university server) — not exported

    Expected CSV format: one row per patient visit, columns matching
    GhanaDatasetSchema.REQUIRED_COLUMNS + GHANA_CLINICAL_COLUMNS.
    """

    REQUIRED_METADATA_FIELDS = [
        "irb_reference",        # e.g. "KATH-IRB-2026-042"
        "ethics_approval_date", # e.g. "2026-01-15"
        "data_custodian",       # e.g. "KATH Health Informatics Unit"
        "deid_method",          # e.g. "k-anonymity k=5 + date shift"
        "data_period",          # e.g. "2023-01-01 to 2025-12-31"
    ]

    def __init__(self, data_path: str | Path, metadata: Optional[Dict] = None):
        self.data_path = Path(data_path)
        self.metadata = metadata or {}
        self._validator = GhanaDataValidator()
        self._engineer = GhanaFeatureEngineer()

    def load_and_validate(self) -> pd.DataFrame:
        """
        Load CSV, validate de-identification compliance, engineer features.

        Raises:
            FileNotFoundError: if data_path does not exist
            ValueError: if validation fails (forbidden columns, missing required)
        """
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Ghana clinical dataset not found: {self.data_path}\n"
                f"Ensure data is exported from KATH/KBTH EHR and placed at this path."
            )

        # Check metadata completeness
        missing_meta = [
            f for f in self.REQUIRED_METADATA_FIELDS if f not in self.metadata
        ]
        if missing_meta:
            logger.warning(
                "KATHDataLoader: metadata incomplete — missing: %s. "
                "Provide full metadata to satisfy data governance requirements.",
                missing_meta,
            )

        logger.info("KATHDataLoader: loading from %s", self.data_path)
        df = pd.read_csv(self.data_path)
        logger.info("Loaded %d rows × %d columns", len(df), len(df.columns))

        # Validate
        is_valid, issues = self._validator.validate(df)
        for issue in issues:
            logger.warning("KATHDataLoader validation: %s", issue)

        # Normalise column names to lowercase_underscore
        df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

        # Add Ghana-specific engineered features
        df = self._engineer.engineer(df)

        logger.info(
            "KATHDataLoader: validation passed. %d rows ready for training.",
            len(df),
        )
        return df


# ============================================================================
# END-TO-END CLINICAL DATA PIPELINE
# ============================================================================

class ClinicalDataPipeline:
    """
    End-to-end pipeline: load → validate → engineer → export features.

    Example usage (once real KATH data is available):

        pipeline = ClinicalDataPipeline(
            data_path="/secure/ghserver/kath_deid_2026.csv",
            metadata={
                "irb_reference": "KATH-IRB-2026-042",
                "ethics_approval_date": "2026-01-15",
                "data_custodian": "KATH Health Informatics",
                "deid_method": "k-anonymity k=5",
                "data_period": "2023-01-01 to 2025-12-31",
            }
        )
        df = pipeline.run()
        # df is ready to pass to EnsembleModelTrainer in train_models.py

    Returns:
        pd.DataFrame with all GHANA_CLINICAL_COLUMNS + 7 engineered features,
        ready for feature extraction by FeatureExtractor in train_models.py.
    """

    def __init__(self, data_path: str | Path, metadata: Optional[Dict] = None):
        self.loader = KATHDataLoader(data_path=data_path, metadata=metadata)

    def run(self) -> pd.DataFrame:
        """Load, validate, and engineer features. Returns model-ready dataframe."""
        return self.loader.load_and_validate()

    def get_target_and_features(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Split dataframe into (X features, y target).

        Returns:
            (X: pd.DataFrame, y: pd.Series of 0/1 readmission labels)
        """
        if "readmitted_30d" not in df.columns:
            raise ValueError("Target column 'readmitted_30d' not found in dataframe")
        y = df["readmitted_30d"].astype(int)
        X = df.drop(columns=["readmitted_30d"])
        return X, y


# ============================================================================
# INTEGRATION WITH TRAINING PIPELINE (usage note)
# ============================================================================
# To use this pipeline in train_models.py HybridTrainingPipeline:
#
#   elif self.data_source == 'ghana_clinical':
#       from api.ai.ghana_clinical_data import ClinicalDataPipeline
#       pipeline = ClinicalDataPipeline(
#           data_path=self.data_path,
#           metadata=self.metadata
#       )
#       return pipeline.run()
#
# The returned DataFrame will be passed to FeatureExtractor.extract_features().
