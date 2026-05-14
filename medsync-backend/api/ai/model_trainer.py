import logging
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix
)
from sklearn.calibration import calibration_curve
from django.conf import settings
from api.models import ModelVersion

logger = logging.getLogger(__name__)

class TrainingResult:
    def __init__(self, model: Any, metrics: Dict[str, Any], evaluation_report: Dict[str, Any]):
        self.model = model
        self.metrics = metrics
        self.evaluation_report = evaluation_report

class ModelTrainer:
    """
    Handles model training, evaluation, and persistence.
    """

    def __init__(self, trained_by_user=None):
        self.trained_by = trained_by_user
        self.model_dir = os.path.join(settings.BASE_DIR, 'api', 'ai', 'models')
        os.makedirs(self.model_dir, exist_ok=True)

    def train_risk_model(self, df: pd.DataFrame, tune_hyperparams: bool = False) -> TrainingResult:
        """
        Trains an XGBoost model for readmission risk.
        """
        X = df.drop(columns=['readmission_30d', 'synthetic_data'], errors='ignore')
        y = df['readmission_30d']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Handle class imbalance
        scale_pos_weight = (len(y) - sum(y)) / sum(y) if sum(y) > 0 else 1

        model = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )

        if tune_hyperparams:
            param_grid = {
                'max_depth': [4, 6, 8],
                'learning_rate': [0.01, 0.1, 0.2]
            }
            grid_search = GridSearchCV(model, param_grid, cv=3, scoring='f1')
            grid_search.fit(X_train, y_train)
            model = grid_search.best_estimator_
        else:
            model.fit(X_train, y_train)

        report = self.evaluate_model(model, X_test, y_test, 'risk_prediction')
        return TrainingResult(model, report['metrics'], report)

    def train_triage_model(self, df: pd.DataFrame) -> TrainingResult:
        """
        Trains an ensemble model for ESI level triage.
        """
        X = df.drop(columns=['esi_level', 'synthetic_data'], errors='ignore')
        y = df['esi_level']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        xgb = XGBClassifier(n_estimators=100, random_state=42, use_label_encoder=False, eval_metric='mlogloss')
        
        ensemble = VotingClassifier(
            estimators=[('rf', rf), ('xgb', xgb)],
            voting='soft'
        )
        ensemble.fit(X_train, y_train)

        report = self.evaluate_model(ensemble, X_test, y_test, 'triage')
        return TrainingResult(ensemble, report['metrics'], report)

    def evaluate_model(self, model: Any, X_test: pd.DataFrame, y_test: pd.Series, model_type: str) -> Dict[str, Any]:
        """
        Generates comprehensive evaluation metrics.
        """
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average='weighted', zero_division=0),
            "recall": recall_score(y_test, y_pred, average='weighted', zero_division=0),
            "f1": f1_score(y_test, y_pred, average='weighted', zero_division=0),
        }

        if len(np.unique(y_test)) == 2:
            metrics["auc_roc"] = roc_auc_score(y_test, y_prob[:, 1])
        
        cm = confusion_matrix(y_test, y_pred).tolist()
        
        report = {
            "metrics": metrics,
            "confusion_matrix": cm,
            "timestamp": datetime.now().isoformat(),
            "model_type": model_type
        }

        if model_type == 'triage':
            # Adjacent accuracy (within 1 ESI level)
            diff = np.abs(y_test.values - y_pred)
            report["adjacent_accuracy"] = float(np.mean(diff <= 1))

        return report

    def compare_with_current(self, new_metrics: Dict[str, Any], model_type: str) -> Dict[str, Any]:
        """
        Compares new model metrics with the current production model.
        """
        current = ModelVersion.objects.filter(model_type=model_type, is_production=True).first()
        if not current:
            return {"status": "no_previous_model", "delta": {}}

        delta = {}
        for k, v in new_metrics.items():
            if k in current.evaluation_metrics:
                delta[k] = v - current.evaluation_metrics[k]

        return {
            "status": "compared",
            "previous_version": current.version_tag,
            "delta": delta
        }

    def save_model_version(self, model: Any, report: Dict[str, Any], model_type: str, data_source: str, sample_count: int) -> ModelVersion:
        """
        Saves the trained model and creates a ModelVersion record.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        version_tag = f"v{timestamp}"
        filename = f"{model_type}_{version_tag}.joblib"
        filepath = os.path.join(self.model_dir, filename)

        joblib.dump(model, filepath)

        # Get comparison
        comparison = self.compare_with_current(report['metrics'], model_type)

        version = ModelVersion.objects.create(
            model_type=model_type,
            version_tag=version_tag,
            trained_by=self.trained_by,
            training_data_source=data_source,
            training_sample_count=sample_count,
            evaluation_metrics=report['metrics'],
            comparison_vs_previous=comparison.get('delta'),
            joblib_path=filepath,
            clinical_use_approved=False,
            is_production=False
        )

        logger.info(f"Saved new {model_type} model version: {version_tag}")
        return version
