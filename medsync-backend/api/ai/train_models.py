"""
Train and persist AI models for MedSync.

Trains on synthetic data by default; can use MIMIC-IV or other CSV if provided.
Saves .joblib files to api/ai/models/ (or MEDSYNC_AI_MODELS_DIR).

Usage:
  python manage.py shell < api/ai/train_models.py
  # or
  cd medsync-backend && python -c "
  import django
  django.setup()
  from api.ai.train_models import run_training
  run_training(data_path=None)
  "

From command line (standalone, no Django DB required for synthetic data):
  python api/ai/train_models.py [--data-csv PATH] [--output-dir DIR]
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import joblib

# Add project root for Django settings if running standalone
try:
    import django
    django.setup()
except Exception:
    pass

from api.ai.model_config import get_models_dir
from api.ai.ml_models.risk_predictor import RiskPredictorModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _synthetic_risk_features(n_samples: int = 2000, seed: int = 42) -> tuple:
    """Generate synthetic feature matrix and per-disease labels for risk prediction."""
    rng = np.random.default_rng(seed)
    diseases = RiskPredictorModel.DISEASES
    features = RiskPredictorModel.REQUIRED_FEATURES
    n_features = len(features)

    X = np.zeros((n_samples, n_features))
    # Aligned with RiskPredictorModel.REQUIRED_FEATURES (26): age, gender x2, blood x5, vitals x6, med x2, allergy/comorbidity x4, conditions x6
    for i in range(n_samples):
        age = rng.integers(18, 85)
        X[i, 0] = age  # age
        X[i, 1] = rng.choice([0, 1])  # gender_male
        X[i, 2] = 1 - X[i, 1]  # gender_female
        for j in range(3, 8):  # blood group one-hot (5: o, a, b, ab, rh_positive)
            X[i, j] = 1 if rng.random() < 0.2 else 0
        if X[i, 3:8].sum() == 0:
            X[i, 3] = 1
        X[i, 8] = 100 + rng.integers(0, 80)   # bp_systolic_mean
        X[i, 9] = 60 + rng.integers(0, 40)   # bp_diastolic_mean
        X[i, 10] = 60 + rng.integers(0, 80)  # pulse_mean
        X[i, 11] = 95 + rng.integers(-5, 5)  # spo2_mean
        X[i, 12] = 60 + rng.integers(0, 50)  # weight_mean
        X[i, 13] = 20 + rng.integers(0, 25)  # bmi_mean
        X[i, 14] = rng.integers(0, 15)      # active_medication_count
        X[i, 15] = rng.integers(0, 50)      # medication_complexity_score
        X[i, 16] = rng.integers(0, 5)       # allergy_count
        X[i, 17] = rng.integers(0, 30)      # allergy_severity_index
        X[i, 18] = rng.integers(0, 15)      # comorbidity_index
        X[i, 19] = rng.integers(0, 10)      # chronic_condition_count
        X[i, 20] = rng.choice([0, 1])       # has_diabetes
        X[i, 21] = rng.choice([0, 1])       # has_hypertension
        X[i, 22] = rng.choice([0, 1])       # has_heart_disease
        X[i, 23] = rng.choice([0, 1])       # has_kidney_disease
        X[i, 24] = rng.choice([0, 1])       # has_copd
        X[i, 25] = rng.choice([0, 1])       # has_asthma

    # Labels: simple rules so models learn something (age + BP + condition flags)
    y_by_disease = {}
    for d, idx in zip(diseases, range(len(diseases))):
        y = np.zeros(n_samples)
        for i in range(n_samples):
            age = X[i, 0]
            bp = X[i, 8]   # bp_systolic_mean
            has_h = X[i, 21]  # has_hypertension
            has_d = X[i, 20]  # has_diabetes
            has_heart = X[i, 22]  # has_heart_disease
            bmi = X[i, 13]
            p = 0.0
            if d == 'heart_disease':
                p = min(1.0, (age - 40) / 100 + (bp - 120) / 400 + has_h * 0.3 + has_heart * 0.5)
            elif d == 'diabetes':
                p = min(1.0, (age - 35) / 80 + (bmi - 22) / 50 + has_d * 0.6)
            elif d == 'hypertension':
                p = min(1.0, (age - 30) / 70 + (bp - 100) / 200 + has_h * 0.5)
            elif d == 'stroke':
                p = min(1.0, (age - 50) / 80 + has_h * 0.4 + (bp - 120) / 300)
            elif d == 'pneumonia':
                p = min(1.0, (age - 60) / 80 + (100 - X[i, 11]) / 50)  # low spo2
            y[i] = 1 if rng.random() < p else 0
        y_by_disease[d] = y

    return X, y_by_disease, features


def _train_risk_predictor(output_dir: Path) -> None:
    """Train per-disease XGBoost classifiers and save to output_dir/risk_predictor.joblib."""
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("xgboost not installed; skipping risk predictor training")
        return

    X, y_by_disease, feature_order = _synthetic_risk_features()
    models = {}
    for disease in RiskPredictorModel.DISEASES:
        y = y_by_disease[disease]
        if np.unique(y).size < 2:
            y[0] = 1 - y[0]
        clf = xgb.XGBClassifier(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
        )
        clf.fit(X, y)
        models[disease] = clf

    payload = {
        'models': models,
        'feature_order': feature_order,
        'version': '1.0',
    }
    out_path = output_dir / 'risk_predictor.joblib'
    joblib.dump(payload, out_path)
    logger.info("Saved risk_predictor.joblib to %s", out_path)


def _train_triage_classifier(output_dir: Path) -> None:
    """Train GradientBoosting classifier for triage level (0=low, 1=medium, 2=high, 3=critical)."""
    from sklearn.ensemble import GradientBoostingClassifier

    rng = np.random.default_rng(43)
    n = 1500
    # Features: vitals-like + chief complaint embedding (fake)
    X = np.column_stack([
        rng.uniform(80, 200, n),   # bp_systolic
        rng.uniform(50, 120, n),   # pulse
        rng.uniform(85, 100, n),  # spo2
        rng.uniform(35, 40, n),   # temp
        rng.uniform(12, 30, n),   # resp_rate
        rng.integers(0, 10, n),   # complaint_embed
    ])
    # Label: critical if spo2 low or bp extreme
    y = np.zeros(n, dtype=int)
    y[(X[:, 2] < 90) | (X[:, 0] > 180)] = 3
    y[(y == 0) & ((X[:, 2] < 94) | (X[:, 0] > 160))] = 2
    y[(y == 0) & ((X[:, 2] < 96) | (X[:, 1] > 110))] = 1
    # Ensure all classes present
    y[0], y[1], y[2], y[3] = 0, 1, 2, 3

    clf = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    clf.fit(X, y)
    payload = {
        'model': clf,
        'feature_names': ['bp_systolic', 'pulse', 'spo2', 'temp', 'resp_rate', 'complaint_embed'],
        'version': '1.0',
    }
    out_path = output_dir / 'triage_classifier.joblib'
    joblib.dump(payload, out_path)
    logger.info("Saved triage_classifier.joblib to %s", out_path)


def _train_diagnosis_classifier(output_dir: Path) -> None:
    """Train RandomForest for diagnosis index (symptom vector -> class)."""
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.default_rng(44)
    n = 1200
    n_diagnoses = 10
    # 20-dim symptom/finding vector
    X = rng.uniform(0, 1, (n, 20))
    y = rng.integers(0, n_diagnoses, n)
    clf = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)
    clf.fit(X, y)
    payload = {
        'model': clf,
        'n_classes': n_diagnoses,
        'version': '1.0',
    }
    out_path = output_dir / 'diagnosis_classifier.joblib'
    joblib.dump(payload, out_path)
    logger.info("Saved diagnosis_classifier.joblib to %s", out_path)


def _train_similarity_matcher(output_dir: Path) -> None:
    """Fit StandardScaler on synthetic feature matrix and save for SimilarityMatcher."""
    from sklearn.preprocessing import StandardScaler
    from api.ai.ml_models.similarity_matcher import SimilarityMatcher

    rng = np.random.default_rng(45)
    n, n_feat = 500, len(SimilarityMatcher.SIMILARITY_FEATURES)
    X = rng.standard_normal((n, n_feat))
    scaler = StandardScaler()
    scaler.fit(X)
    payload = {
        'scaler': scaler,
        'feature_names': SimilarityMatcher.SIMILARITY_FEATURES,
        'version': '1.0',
    }
    out_path = output_dir / 'similarity_matcher.joblib'
    joblib.dump(payload, out_path)
    logger.info("Saved similarity_matcher.joblib to %s", out_path)


def run_training(data_path: str | None = None, output_dir: Path | None = None) -> None:
    """
    Train all models and save to output_dir (default: get_models_dir()).
    data_path: optional CSV path for future MIMIC-IV; currently ignored, uses synthetic data.
    """
    out = output_dir or get_models_dir()
    out.mkdir(parents=True, exist_ok=True)
    if data_path:
        logger.info("Data path %s provided; CSV loading not yet implemented, using synthetic data", data_path)
    _train_risk_predictor(out)
    _train_triage_classifier(out)
    _train_diagnosis_classifier(out)
    _train_similarity_matcher(out)
    logger.info("Training complete. Models in %s", out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train MedSync AI models")
    parser.add_argument("--data-csv", default=None, help="Path to training CSV (e.g. MIMIC-IV); not yet used")
    parser.add_argument("--output-dir", default=None, help="Output directory for .joblib files")
    args = parser.parse_args()
    out = Path(args.output_dir).resolve() if args.output_dir else None
    run_training(data_path=args.data_csv, output_dir=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
