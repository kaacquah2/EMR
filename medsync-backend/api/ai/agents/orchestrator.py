"""Risk-only AI orchestrator for MedSync."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from api.ai.clinical_validation import get_clinical_disclaimer
from api.ai.ml_models import get_risk_predictor

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """Thin wrapper around the active risk predictor."""

    def __init__(self):
        self.model_metadata = {
            "version": "risk-only",
            "created_at": datetime.now().isoformat(),
            "execution_mode": "single_model",
            "clinical_readiness": "DEMONSTRATION_ONLY",
        }
        logger.info("AI Orchestrator initialized in risk-only mode")

    def run_risk_assessment(
        self,
        patient_data: Dict[str, Any],
        features: Dict[str, Any],
        chief_complaint: str = "",
    ) -> Dict[str, Any]:
        """Run the active risk predictor and shape a compact response."""
        try:
            patient_id = str(features.get("patient_id") or patient_data.get("demographics", {}).get("patient_id", "unknown"))
            predictor = get_risk_predictor()
            prediction = predictor.predict_risk(features)
            top_risk = prediction.get("top_risk_disease", "unknown")
            top_score = prediction.get("top_risk_score", 0)

            recommendations = []
            if top_score >= 80:
                recommendations.append("Escalate for urgent clinical review")
            elif top_score >= 60:
                recommendations.append("Review risk factors and monitor closely")
            else:
                recommendations.append("Continue routine monitoring")

            summary = (
                f"Risk-only assessment for {patient_id}. "
                f"Top signal: {top_risk} at {top_score:.0f}%."
            )

            result = {
                "patient_id": patient_id,
                "analysis_timestamp": datetime.now().isoformat(),
                "agents_executed": ["risk_agent", "summary_agent"],
                "risk_analysis": prediction,
                "triage_assessment": None,
                "diagnosis_suggestions": None,
                "similar_patients": None,
                "referral_recommendations": None,
                "clinical_summary": summary,
                "recommended_actions": recommendations,
                "alerts": recommendations[:1] if top_score >= 80 else [],
                "confidence_score": prediction.get("confidence_score", 0.5),
                "demo_mode": True,
                "disclaimer": get_clinical_disclaimer(),
                "clinical_validation_status": "SYNTHETIC_ONLY",
                "metrics": {
                    "execution_mode": "single_model",
                    "active_model": "risk_predictor",
                },
            }
            return result
        except Exception as e:
            logger.error("Risk assessment failed: %s", e)
            raise

    def analyze_patient_comprehensive(
        self,
        patient_data: Dict[str, Any],
        features: Dict[str, Any],
        chief_complaint: str = "",
        include_similarity: bool = True,
        include_referral: bool = True,
    ) -> Dict[str, Any]:
        """Backward-compatible wrapper that now runs risk-only assessment."""
        return self.run_risk_assessment(patient_data, features, chief_complaint=chief_complaint)


_orchestrator: Optional[AIOrchestrator] = None


def get_orchestrator() -> AIOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator()
    return _orchestrator
