"""
AI Services Layer - High-level service classes for AI features.

Provides:
- RiskPredictionService
- DiagnosisService
- TriageService
- SimilaritySearchService
- ReferralRecommendationService
"""

from .services import (
    BaseAIService,
    AIServiceException,
    RiskPredictionService,
    DiagnosisService,
    TriageService,
    SimilaritySearchService,
    ReferralRecommendationService,
)

__all__ = [
    'BaseAIService',
    'AIServiceException',
    'RiskPredictionService',
    'DiagnosisService',
    'TriageService',
    'SimilaritySearchService',
    'ReferralRecommendationService',
]
