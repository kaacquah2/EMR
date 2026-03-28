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


def _load_model(path: str) -> Any:
    """Load a pickled model from disk with basic validation."""
    if not os.path.exists(path):
        raise ImproperlyConfigured(f"AI model file not found: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def get_risk_predictor():
    from .risk_predictor import RiskPredictorModel

    path = settings.MODEL_PATHS["risk_predictor"]
    model = _load_model(path)
    if not isinstance(model, RiskPredictorModel):
        raise ImproperlyConfigured("Loaded risk predictor model has unexpected type")
    return model


def get_diagnosis_classifier():
    from .diagnosis_classifier import DiagnosisClassifier

    path = settings.MODEL_PATHS["diagnosis_classifier"]
    model = _load_model(path)
    if not isinstance(model, DiagnosisClassifier):
        raise ImproperlyConfigured("Loaded diagnosis classifier model has unexpected type")
    return model


def get_triage_classifier():
    from .triage_classifier import TriageClassifier

    path = settings.MODEL_PATHS["triage_classifier"]
    model = _load_model(path)
    if not isinstance(model, TriageClassifier):
        raise ImproperlyConfigured("Loaded triage classifier model has unexpected type")
    return model


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
