import os
import joblib
import logging
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class ModelRegistry:
    """
    In-memory registry and cache for AI models.
    Prevents repeated disk I/O when loading .joblib models.
    """
    
    _instance = None
    _models: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelRegistry, cls).__new__(cls)
        return cls._instance

    def get_model(self, model_name: str, model_path: Optional[str] = None) -> Any:
        """
        Retrieve a model from cache or load it from disk.
        
        Args:
            model_name: Identifier for the model (e.g., 'risk_predictor')
            model_path: Full path to the .joblib file
            
        Returns:
            The loaded model object
        """
        if model_name in self._models:
            return self._models[model_name]
            
        if model_path is None:
            model_path = self._get_default_path(model_name)
            
        if not model_path or not os.path.exists(model_path):
            logger.error(f"Model path not found: {model_path}")
            return None
            
        try:
            logger.info(f"Loading model '{model_name}' from {model_path} into memory...")
            model = joblib.load(model_path)
            self._models[model_name] = model
            return model
        except Exception as e:
            logger.error(f"Failed to load model '{model_name}': {e}")
            return None

    def _get_default_path(self, model_name: str) -> Optional[str]:
        """Resolve default paths for core MedSync models."""
        base_ai_dir = os.path.join(settings.BASE_DIR, 'api', 'ai', 'models')
        model_version = getattr(settings, 'AI_MODEL_VERSION', '1.0.0-hybrid')
        
        version_dir = os.path.join(base_ai_dir, f"v{model_version}")
        
        # Mapping model names to filenames
        mapping = {
            'risk_predictor': 'xgboost.joblib',
            'triage_classifier': 'triage_classifier.joblib',
            'diagnosis_classifier': 'diagnosis_classifier.joblib',
            'similarity_matcher': 'similarity_matcher.joblib',
            'scaler': 'scaler.joblib'
        }
        
        filename = mapping.get(model_name)
        if filename:
            return os.path.join(version_dir, filename)
            
        # Fallback to root models if versioned not found
        return os.path.join(base_ai_dir, f"{model_name}.joblib")

    def clear_cache(self):
        """Clear all loaded models from memory."""
        self._models.clear()
        logger.info("Model registry cache cleared.")

# Singleton accessor
def get_model_registry() -> ModelRegistry:
    return ModelRegistry()
