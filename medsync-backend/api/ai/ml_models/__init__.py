"""ML model loaders for the active MedSync risk predictor."""

from __future__ import annotations

import os
import pickle
from typing import Any

def get_risk_predictor():
    from .risk_predictor import get_risk_predictor as _get_rp

    return _get_rp()

def __getattr__(name: str) -> Any:
    if name == "RiskPredictorModel":
        from .risk_predictor import RiskPredictorModel

        return RiskPredictorModel

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RiskPredictorModel",
    "get_risk_predictor",
]
