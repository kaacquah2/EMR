"""
ML Models submodule - Disease Risk Prediction, Clinical Decision Support, etc.

Delegates to the singleton factory functions defined in each model module so that
model instances are created (and joblib payloads are loaded) exactly once per
process lifetime.  Heavy dependencies (numpy, scikit-learn) are not imported at
module load so slim deploys (e.g. Vercel without ML wheels) can still import the
Django app.
"""

from __future__ import annotations

from typing import Any


def get_risk_predictor():
    from .risk_predictor import get_risk_predictor as _grp

    return _grp()


def get_diagnosis_classifier():
    from .diagnosis_classifier import get_diagnosis_classifier as _gdc

    return _gdc()


def get_triage_classifier():
    from .triage_classifier import get_triage_classifier as _gtc

    return _gtc()


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
