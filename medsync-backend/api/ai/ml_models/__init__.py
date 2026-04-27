"""
ML Models submodule - Disease Risk Prediction, Clinical Decision Support, etc.

Provides environment-aware wrappers for loading pickled ML models from paths
configured in Django settings (MEDIUM-4).

Heavy dependencies (numpy, scikit-learn) are not imported at module load so slim
deploys (e.g. Vercel without ML wheels) can still import the Django app.
"""

from __future__ import annotations

import os
import pickle
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _load_model(path: str, model_name: str = 'unknown') -> Any:
    """Load a model via ModelRegistry (uses in-memory cache)."""
    from api.ai.model_registry import get_model_registry
    registry = get_model_registry()
    return registry.get_model(model_name, model_path=path)


def get_risk_predictor():
    from .risk_predictor import get_risk_predictor as _get_rp

    return _get_rp()


def get_diagnosis_classifier():
    from .diagnosis_classifier import get_diagnosis_classifier as _get_dc

    return _get_dc()


def get_triage_classifier():
    from .triage_classifier import get_triage_classifier as _get_tc

    return _get_tc()


def get_similarity_matcher():
    from .similarity_matcher import get_similarity_matcher as _gsm

    return _gsm()


def __getattr__(name: str) -> Any:
    if name == "RiskPredictorModel":
        from .risk_predictor import RiskPredictorModel

        return RiskPredictorModel
    if name == "DiagnosisClassifier":
        from .diagnosis_classifier import DiagnosisClassifier

        return DiagnosisClassifier
    if name == "TriageClassifier":
        from .triage_classifier import TriageClassifier

        return TriageClassifier
    if name == "SimilarityMatcher":
        from .similarity_matcher import SimilarityMatcher

        return SimilarityMatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RiskPredictorModel",
    "get_risk_predictor",
    "DiagnosisClassifier",
    "get_diagnosis_classifier",
    "TriageClassifier",
    "get_triage_classifier",
    "SimilarityMatcher",
    "get_similarity_matcher",
]
