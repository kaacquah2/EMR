"""
Clinical Validation Harness for MedSync AI Models.

Defines the requirements for production clinical deployment and tracks
the current validation status of each model. This module makes the
demo-only status **programmatic** — every AI response can query it
to include accurate provenance and readiness metadata.

Readiness Levels:
    0 - UNVALIDATED: Model exists but has no validation whatsoever.
    1 - SYNTHETIC_ONLY: Validated on synthetic/generated data only.
    2 - PUBLIC_DATASET: Validated on public datasets (UCI, MIMIC-IV).
    3 - RETROSPECTIVE_CLINICAL: Validated on retrospective clinical data.
    4 - PROSPECTIVE_CLINICAL: Validated in prospective clinical trial.
    5 - PRODUCTION_APPROVED: Approved for clinical decision support.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ReadinessLevel(IntEnum):
    """Clinical readiness levels for AI models."""
    UNVALIDATED = 0
    SYNTHETIC_ONLY = 1
    PUBLIC_DATASET = 2
    RETROSPECTIVE_CLINICAL = 3
    PROSPECTIVE_CLINICAL = 4
    PRODUCTION_APPROVED = 5


# Human-readable labels
READINESS_LABELS = {
    ReadinessLevel.UNVALIDATED: "Unvalidated",
    ReadinessLevel.SYNTHETIC_ONLY: "Synthetic Data Only — DEMONSTRATION",
    ReadinessLevel.PUBLIC_DATASET: "Public Dataset Validated — NOT CLINICAL",
    ReadinessLevel.RETROSPECTIVE_CLINICAL: "Retrospective Clinical Validation",
    ReadinessLevel.PROSPECTIVE_CLINICAL: "Prospective Clinical Trial",
    ReadinessLevel.PRODUCTION_APPROVED: "Production Approved",
}


@dataclass
class DataProvenance:
    """Track exactly what data trained a model."""
    source_name: str
    source_type: str  # 'synthetic', 'public_dataset', 'clinical'
    record_count: int
    description: str
    url: Optional[str] = None
    license: Optional[str] = None
    date_acquired: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_name': self.source_name,
            'source_type': self.source_type,
            'record_count': self.record_count,
            'description': self.description,
            'url': self.url,
            'license': self.license,
            'date_acquired': self.date_acquired,
        }


@dataclass
class ModelValidationRecord:
    """Validation record for a single model."""
    model_name: str
    model_version: str
    readiness_level: ReadinessLevel
    data_sources: List[DataProvenance] = field(default_factory=list)
    validation_metrics: Dict[str, float] = field(default_factory=dict)
    known_limitations: List[str] = field(default_factory=list)
    regulatory_status: str = "NOT_SUBMITTED"
    last_validated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'model_version': self.model_version,
            'readiness_level': self.readiness_level.value,
            'readiness_label': READINESS_LABELS[self.readiness_level],
            'data_sources': [ds.to_dict() for ds in self.data_sources],
            'validation_metrics': self.validation_metrics,
            'known_limitations': self.known_limitations,
            'regulatory_status': self.regulatory_status,
            'last_validated': self.last_validated,
        }


# ── Current model registry with honest provenance ──────────────────────

SYNTHETIC_GHANA = DataProvenance(
    source_name="Ghana Synthetic Cohort",
    source_type="synthetic",
    record_count=2000,
    description=(
        "Randomly generated patient data using numpy. Ghana-specific disease "
        "prevalence rates (malaria 25%, sickle cell 2%, etc.) but NO real "
        "patient data. Vitals, labs, and outcomes are all simulated."
    ),
    url=None,
    license="Internal — generated code",
)

SYNTHETIC_UCI_FALLBACK = DataProvenance(
    source_name="UCI Readmission (Synthetic Fallback)",
    source_type="synthetic",
    record_count=5000,
    description=(
        "Synthetic data generated to match UCI Hospital Readmission schema. "
        "NOT the actual UCI dataset — the downloader falls back to random "
        "generation when the real dataset is unavailable."
    ),
    url="https://archive.ics.uci.edu/dataset/296",
    license="CC BY 4.0 (original dataset)",
)


# Current validation records for all MedSync models
MODEL_VALIDATION_REGISTRY: Dict[str, ModelValidationRecord] = {
    'risk_predictor': ModelValidationRecord(
        model_name='Risk Predictor (XGBoost Ensemble)',
        model_version='1.0.0-hybrid',
        readiness_level=ReadinessLevel.SYNTHETIC_ONLY,
        data_sources=[SYNTHETIC_GHANA, SYNTHETIC_UCI_FALLBACK],
        validation_metrics={
            'auc_roc': 0.0,  # Populated at training time
            'sensitivity': 0.0,
            'specificity': 0.0,
        },
        known_limitations=[
            "Trained entirely on synthetic (random) data",
            "No clinical validation performed",
            "Disease prevalence rates are assumed, not measured",
            "Feature distributions do not reflect real patient populations",
            "Readmission target is simulated via simple threshold rules",
            "Cannot be used for actual clinical risk decisions",
        ],
    ),
    'triage_classifier': ModelValidationRecord(
        model_name='Triage Classifier (GradientBoosting)',
        model_version='1.0',
        readiness_level=ReadinessLevel.SYNTHETIC_ONLY,
        data_sources=[SYNTHETIC_GHANA],
        known_limitations=[
            "Trained on 1500 randomly generated samples",
            "Triage labels derived from simple threshold rules on synthetic vitals",
            "Does not reflect real emergency department triage patterns",
            "ESI levels are approximated, not clinically validated",
        ],
    ),
    'diagnosis_classifier': ModelValidationRecord(
        model_name='Diagnosis Classifier (RandomForest)',
        model_version='1.0',
        readiness_level=ReadinessLevel.SYNTHETIC_ONLY,
        data_sources=[SYNTHETIC_GHANA],
        known_limitations=[
            "Trained on 1200 random feature vectors → random class labels",
            "Diagnosis classes are arbitrary indices, not real ICD-10 mappings",
            "Zero clinical evidence basis",
        ],
    ),
    'similarity_matcher': ModelValidationRecord(
        model_name='Similarity Matcher (StandardScaler + FAISS)',
        model_version='1.0',
        readiness_level=ReadinessLevel.SYNTHETIC_ONLY,
        data_sources=[SYNTHETIC_GHANA],
        known_limitations=[
            "Scaler fitted on random normal data",
            "Similarity scores not validated against clinical similarity judgments",
        ],
    ),
}


class ClinicalValidationChecklist:
    """
    Defines what is required before models can be used clinically.

    This checklist documents the gap between current state (synthetic demo)
    and production readiness, so future teams know exactly what to do.
    """

    REQUIREMENTS = [
        {
            'id': 'DATA-001',
            'category': 'Data',
            'requirement': 'Train on de-identified clinical dataset (e.g., MIMIC-IV, eICU)',
            'status': 'NOT_STARTED',
            'priority': 'CRITICAL',
            'notes': 'Requires PhysioNet credentialed access and IRB approval',
        },
        {
            'id': 'DATA-002',
            'category': 'Data',
            'requirement': 'Validate on Ghana-specific clinical data',
            'status': 'NOT_STARTED',
            'priority': 'CRITICAL',
            'notes': 'Requires partnership with Ghanaian health facility',
        },
        {
            'id': 'VAL-001',
            'category': 'Validation',
            'requirement': 'Retrospective validation on held-out clinical data',
            'status': 'NOT_STARTED',
            'priority': 'CRITICAL',
            'notes': 'AUC-ROC > 0.80, sensitivity > 0.75 required',
        },
        {
            'id': 'VAL-002',
            'category': 'Validation',
            'requirement': 'Subgroup fairness analysis (age, gender, ethnicity)',
            'status': 'NOT_STARTED',
            'priority': 'HIGH',
            'notes': 'Ensure no disparate impact across demographics',
        },
        {
            'id': 'VAL-003',
            'category': 'Validation',
            'requirement': 'Prospective pilot study (shadow mode)',
            'status': 'NOT_STARTED',
            'priority': 'HIGH',
            'notes': 'Run alongside clinician decisions without affecting care',
        },
        {
            'id': 'MON-001',
            'category': 'Monitoring',
            'requirement': 'Production drift detection operational',
            'status': 'IN_PROGRESS',
            'priority': 'HIGH',
            'notes': 'ModelMonitor module being implemented',
        },
        {
            'id': 'REG-001',
            'category': 'Regulatory',
            'requirement': 'Ghana FDA / institutional review approval',
            'status': 'NOT_STARTED',
            'priority': 'CRITICAL',
            'notes': 'Required before any clinical deployment',
        },
        {
            'id': 'REG-002',
            'category': 'Regulatory',
            'requirement': 'Clinical safety risk assessment',
            'status': 'NOT_STARTED',
            'priority': 'CRITICAL',
            'notes': 'IEC 62304 / ISO 14971 compliance evaluation',
        },
    ]

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get overall clinical validation status."""
        total = len(cls.REQUIREMENTS)
        completed = sum(1 for r in cls.REQUIREMENTS if r['status'] == 'COMPLETED')
        critical_incomplete = sum(
            1 for r in cls.REQUIREMENTS
            if r['priority'] == 'CRITICAL' and r['status'] != 'COMPLETED'
        )

        return {
            'overall_status': 'NOT_READY' if critical_incomplete > 0 else 'READY',
            'total_requirements': total,
            'completed': completed,
            'critical_incomplete': critical_incomplete,
            'completion_pct': round((completed / total) * 100, 1) if total > 0 else 0,
            'requirements': cls.REQUIREMENTS,
        }


def get_model_provenance(model_name: str) -> Dict[str, Any]:
    """
    Get provenance and validation status for a model.

    Use this in every AI response to provide honest metadata.
    """
    record = MODEL_VALIDATION_REGISTRY.get(model_name)
    if record is None:
        return {
            'model_name': model_name,
            'readiness_level': ReadinessLevel.UNVALIDATED.value,
            'readiness_label': READINESS_LABELS[ReadinessLevel.UNVALIDATED],
            'clinical_disclaimer': (
                "⚠️ DEMONSTRATION ONLY — This model has no validation record. "
                "NOT for clinical use."
            ),
        }

    result = record.to_dict()
    result['clinical_disclaimer'] = _build_disclaimer(record)
    return result


def get_clinical_disclaimer() -> str:
    """Standard clinical disclaimer for all AI responses."""
    return (
        "⚠️ DEMONSTRATION ONLY — Models are trained on synthetic data and have "
        "NOT been validated on real clinical data. These predictions MUST NOT be "
        "used for clinical decision-making. Always rely on qualified clinical judgment."
    )


def _build_disclaimer(record: ModelValidationRecord) -> str:
    """Build model-specific disclaimer based on readiness level."""
    if record.readiness_level <= ReadinessLevel.SYNTHETIC_ONLY:
        return (
            f"⚠️ DEMONSTRATION ONLY — {record.model_name} is trained on "
            f"synthetic data only. NOT for clinical use."
        )
    elif record.readiness_level <= ReadinessLevel.PUBLIC_DATASET:
        return (
            f"⚠️ RESEARCH USE ONLY — {record.model_name} has been validated "
            f"on public datasets but NOT on clinical data."
        )
    elif record.readiness_level <= ReadinessLevel.RETROSPECTIVE_CLINICAL:
        return (
            f"⚠️ INVESTIGATIONAL — {record.model_name} has retrospective "
            f"clinical validation. Prospective study required."
        )
    elif record.readiness_level <= ReadinessLevel.PROSPECTIVE_CLINICAL:
        return (
            f"ℹ️ VALIDATED — {record.model_name} has been clinically validated. "
            f"Pending regulatory approval."
        )
    else:
        return f"✅ APPROVED — {record.model_name} is approved for clinical use."
