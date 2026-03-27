"""
ML Models submodule - Disease Risk Prediction, Clinical Decision Support, etc.

Provides environment-aware wrappers for loading pickled ML models from paths
configured in Django settings (MEDIUM-4).
"""

import os
import pickle
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .risk_predictor import RiskPredictorModel
from .diagnosis_classifier import DiagnosisClassifier
from .triage_classifier import TriageClassifier
from .similarity_matcher import SimilarityMatcher, get_similarity_matcher


def _load_model(path: str) -> Any:
    """Load a pickled model from disk with basic validation."""
    if not os.path.exists(path):
        raise ImproperlyConfigured(f"AI model file not found: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def get_risk_predictor() -> RiskPredictorModel:
    path = settings.MODEL_PATHS["risk_predictor"]
    model = _load_model(path)
    if not isinstance(model, RiskPredictorModel):
        raise ImproperlyConfigured("Loaded risk predictor model has unexpected type")
    return model


def get_diagnosis_classifier() -> DiagnosisClassifier:
    path = settings.MODEL_PATHS["diagnosis_classifier"]
    model = _load_model(path)
    if not isinstance(model, DiagnosisClassifier):
        raise ImproperlyConfigured("Loaded diagnosis classifier model has unexpected type")
    return model


def get_triage_classifier() -> TriageClassifier:
    path = settings.MODEL_PATHS["triage_classifier"]
    model = _load_model(path)
    if not isinstance(model, TriageClassifier):
        raise ImproperlyConfigured("Loaded triage classifier model has unexpected type")
    return model


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
