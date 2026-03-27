"""
Paths and config for serialized ML models.

Models are stored under api/ai/models/ as .joblib files.
Use get_models_dir() so tests and train_models can override via env.
"""

import os
from pathlib import Path

# Directory containing this file (api/ai/)
_AI_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = _AI_DIR / "models"


def get_models_dir() -> Path:
    """Return directory for serialized model files. Respects MEDSYNC_AI_MODELS_DIR if set."""
    path = os.environ.get("MEDSYNC_AI_MODELS_DIR")
    if path:
        return Path(path).resolve()
    return DEFAULT_MODELS_DIR
