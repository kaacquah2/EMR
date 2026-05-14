"""
AI Model Performance Monitor for MedSync.

Tracks model predictions over time and detects drift in both input
features and output distributions. Uses Population Stability Index (PSI)
for distribution comparison and stores results for dashboarding.

Components:
- PredictionRecorder: Buffers recent predictions in Redis/cache
- DriftDetector: Computes PSI between baseline and recent windows
- ModelMonitor: High-level API combining recording and detection
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

import numpy as np

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

# PSI thresholds (industry standard)
PSI_THRESHOLD_WARNING = 0.10   # Moderate drift — investigate
PSI_THRESHOLD_CRITICAL = 0.25  # Severe drift — consider retraining

# How many recent predictions to buffer per model
PREDICTION_BUFFER_SIZE = 1000

# Cache TTL for prediction buffers (7 days)
PREDICTION_BUFFER_TTL = 60 * 60 * 24 * 7


class DriftDetector:
    """
    Detect distribution shift using Population Stability Index (PSI).

    PSI measures the difference between two distributions:
    - PSI < 0.10: No significant drift
    - 0.10 <= PSI < 0.25: Moderate drift — investigate
    - PSI >= 0.25: Significant drift — retrain model

    Formula: PSI = Σ (p_new - p_baseline) × ln(p_new / p_baseline)
    """

    @staticmethod
    def calculate_psi(
        baseline: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10,
    ) -> float:
        """
        Calculate PSI between baseline and current distributions.

        Args:
            baseline: Reference distribution (from training)
            current: Recent distribution (from production)
            n_bins: Number of histogram bins

        Returns:
            PSI value (0 = identical, higher = more drift)
        """
        if len(baseline) < 2 or len(current) < 2:
            return 0.0

        # Create bins from baseline
        _, bin_edges = np.histogram(baseline, bins=n_bins)

        # Count in each bin (add small epsilon to avoid division by zero)
        eps = 1e-6
        baseline_counts = np.histogram(baseline, bins=bin_edges)[0] + eps
        current_counts = np.histogram(current, bins=bin_edges)[0] + eps

        # Normalize to proportions
        baseline_pct = baseline_counts / baseline_counts.sum()
        current_pct = current_counts / current_counts.sum()

        # PSI formula
        psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))

        return float(psi)

    @staticmethod
    def interpret_psi(psi_value: float) -> Dict[str, Any]:
        """Interpret a PSI value into actionable guidance."""
        if psi_value < PSI_THRESHOLD_WARNING:
            return {
                'level': 'OK',
                'message': 'No significant drift detected.',
                'action': 'Continue monitoring.',
            }
        elif psi_value < PSI_THRESHOLD_CRITICAL:
            return {
                'level': 'WARNING',
                'message': f'Moderate drift detected (PSI={psi_value:.4f}).',
                'action': 'Investigate feature distributions. Consider retraining if trend continues.',
            }
        else:
            return {
                'level': 'CRITICAL',
                'message': f'Significant drift detected (PSI={psi_value:.4f}).',
                'action': 'Model predictions may be unreliable. Recommend retraining.',
            }


class PredictionRecorder:
    """
    Buffer recent predictions in cache for drift analysis.

    Stores feature vectors and prediction outputs keyed by model name.
    Uses Redis/Django cache backend for persistence across requests.
    """

    @staticmethod
    def _cache_key(model_name: str, data_type: str) -> str:
        """Generate cache key for a model's prediction buffer."""
        return f"model_monitor:{model_name}:{data_type}"

    @staticmethod
    def record_prediction(
        model_name: str,
        features: Dict[str, Any],
        prediction: Dict[str, Any],
    ) -> None:
        """
        Record a prediction for monitoring.

        Args:
            model_name: Name of the model (e.g., 'risk_predictor')
            features: Input feature dict
            prediction: Output prediction dict
        """
        try:
            timestamp = datetime.now().isoformat()

            # Record features
            features_key = PredictionRecorder._cache_key(model_name, 'features')
            feature_buffer = cache.get(features_key, [])

            # Extract numeric features for drift analysis
            numeric_features = {}
            for k, v in features.items():
                if isinstance(v, (int, float)):
                    numeric_features[k] = v

            feature_buffer.append({
                'timestamp': timestamp,
                'features': numeric_features,
            })

            # Cap buffer size
            if len(feature_buffer) > PREDICTION_BUFFER_SIZE:
                feature_buffer = feature_buffer[-PREDICTION_BUFFER_SIZE:]

            cache.set(features_key, feature_buffer, PREDICTION_BUFFER_TTL)

            # Record predictions
            pred_key = PredictionRecorder._cache_key(model_name, 'predictions')
            pred_buffer = cache.get(pred_key, [])

            # Extract key prediction values
            pred_summary = {
                'timestamp': timestamp,
                'top_risk_score': prediction.get('top_risk_score'),
                'confidence_score': prediction.get('confidence_score')
                    or prediction.get('confidence'),
                'triage_level': prediction.get('triage_level'),
            }
            pred_buffer.append(pred_summary)

            if len(pred_buffer) > PREDICTION_BUFFER_SIZE:
                pred_buffer = pred_buffer[-PREDICTION_BUFFER_SIZE:]

            cache.set(pred_key, pred_buffer, PREDICTION_BUFFER_TTL)

        except Exception as e:
            # Monitoring should never break the main prediction path
            logger.warning(f"Failed to record prediction for {model_name}: {e}")

    @staticmethod
    def get_feature_buffer(model_name: str) -> List[Dict]:
        """Get the feature buffer for a model."""
        key = PredictionRecorder._cache_key(model_name, 'features')
        return cache.get(key, [])

    @staticmethod
    def get_prediction_buffer(model_name: str) -> List[Dict]:
        """Get the prediction buffer for a model."""
        key = PredictionRecorder._cache_key(model_name, 'predictions')
        return cache.get(key, [])


class ModelMonitor:
    """
    High-level model monitoring API.

    Combines prediction recording, drift detection, and reporting.
    """

    MONITORED_MODELS = [
        'risk_predictor',
        'triage_classifier',
        'diagnosis_classifier',
        'similarity_matcher',
    ]

    def __init__(self):
        self.drift_detector = DriftDetector()
        self.recorder = PredictionRecorder()

    def record_prediction(
        self,
        model_name: str,
        features: Dict[str, Any],
        prediction: Dict[str, Any],
    ) -> None:
        """Record a prediction for monitoring."""
        self.recorder.record_prediction(model_name, features, prediction)

    def check_input_drift(
        self,
        model_name: str,
        baseline_features: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Check for input feature drift.

        Compares the distribution of recent input features against a
        baseline (first half of buffer or provided baseline).

        Args:
            model_name: Model to check
            baseline_features: Optional baseline feature buffer.
                If None, uses the first half of the current buffer.

        Returns:
            Drift report dict with per-feature PSI values
        """
        buffer = self.recorder.get_feature_buffer(model_name)

        if len(buffer) < 20:
            return {
                'model_name': model_name,
                'status': 'INSUFFICIENT_DATA',
                'message': f'Only {len(buffer)} predictions recorded. Need at least 20.',
                'checked_at': datetime.now().isoformat(),
            }

        # Split buffer into baseline (first half) and current (second half)
        midpoint = len(buffer) // 2
        if baseline_features:
            baseline_data = baseline_features
            current_data = buffer
        else:
            baseline_data = buffer[:midpoint]
            current_data = buffer[midpoint:]

        # Collect all feature names
        all_features = set()
        for entry in baseline_data + current_data:
            all_features.update(entry.get('features', {}).keys())

        # Calculate PSI per feature
        feature_drift = {}
        max_psi = 0.0

        for feature_name in sorted(all_features):
            baseline_vals = np.array([
                entry['features'].get(feature_name, 0)
                for entry in baseline_data
                if feature_name in entry.get('features', {})
            ])
            current_vals = np.array([
                entry['features'].get(feature_name, 0)
                for entry in current_data
                if feature_name in entry.get('features', {})
            ])

            if len(baseline_vals) < 5 or len(current_vals) < 5:
                continue

            psi = self.drift_detector.calculate_psi(baseline_vals, current_vals)
            interpretation = self.drift_detector.interpret_psi(psi)

            feature_drift[feature_name] = {
                'psi': round(psi, 6),
                **interpretation,
            }
            max_psi = max(max_psi, psi)

        # Overall status
        overall = self.drift_detector.interpret_psi(max_psi)

        return {
            'model_name': model_name,
            'status': overall['level'],
            'message': overall['message'],
            'action': overall['action'],
            'max_psi': round(max_psi, 6),
            'feature_drift': feature_drift,
            'baseline_size': len(baseline_data),
            'current_size': len(current_data),
            'checked_at': datetime.now().isoformat(),
        }

    def check_prediction_drift(self, model_name: str) -> Dict[str, Any]:
        """
        Check for prediction output drift.

        Detects shifts in the distribution of prediction scores/outputs.
        """
        buffer = self.recorder.get_prediction_buffer(model_name)

        if len(buffer) < 20:
            return {
                'model_name': model_name,
                'status': 'INSUFFICIENT_DATA',
                'message': f'Only {len(buffer)} predictions recorded. Need at least 20.',
                'checked_at': datetime.now().isoformat(),
            }

        midpoint = len(buffer) // 2
        baseline = buffer[:midpoint]
        current = buffer[midpoint:]

        # Check risk score drift
        drift_metrics = {}

        # Risk scores
        baseline_scores = np.array([
            b['top_risk_score'] for b in baseline
            if b.get('top_risk_score') is not None
        ])
        current_scores = np.array([
            c['top_risk_score'] for c in current
            if c.get('top_risk_score') is not None
        ])

        if len(baseline_scores) >= 5 and len(current_scores) >= 5:
            psi = self.drift_detector.calculate_psi(baseline_scores, current_scores)
            drift_metrics['risk_score'] = {
                'psi': round(psi, 6),
                'baseline_mean': round(float(baseline_scores.mean()), 4),
                'current_mean': round(float(current_scores.mean()), 4),
                **self.drift_detector.interpret_psi(psi),
            }

        # Confidence scores
        baseline_conf = np.array([
            b['confidence_score'] for b in baseline
            if b.get('confidence_score') is not None
        ])
        current_conf = np.array([
            c['confidence_score'] for c in current
            if c.get('confidence_score') is not None
        ])

        if len(baseline_conf) >= 5 and len(current_conf) >= 5:
            psi = self.drift_detector.calculate_psi(baseline_conf, current_conf)
            drift_metrics['confidence_score'] = {
                'psi': round(psi, 6),
                'baseline_mean': round(float(baseline_conf.mean()), 4),
                'current_mean': round(float(current_conf.mean()), 4),
                **self.drift_detector.interpret_psi(psi),
            }

        max_psi = max(
            (m['psi'] for m in drift_metrics.values()),
            default=0.0
        )
        overall = self.drift_detector.interpret_psi(max_psi)

        return {
            'model_name': model_name,
            'status': overall['level'],
            'message': overall['message'],
            'action': overall['action'],
            'max_psi': round(max_psi, 6),
            'prediction_drift': drift_metrics,
            'baseline_size': len(baseline),
            'current_size': len(current),
            'checked_at': datetime.now().isoformat(),
        }

    def get_monitoring_report(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive monitoring report.

        Args:
            model_name: Specific model to report on, or None for all models

        Returns:
            Monitoring report dict
        """
        models_to_check = [model_name] if model_name else self.MONITORED_MODELS
        reports = {}

        for name in models_to_check:
            input_drift = self.check_input_drift(name)
            pred_drift = self.check_prediction_drift(name)

            feature_buffer = self.recorder.get_feature_buffer(name)
            pred_buffer = self.recorder.get_prediction_buffer(name)

            reports[name] = {
                'input_drift': input_drift,
                'prediction_drift': pred_drift,
                'predictions_recorded': len(pred_buffer),
                'features_recorded': len(feature_buffer),
                'oldest_record': feature_buffer[0]['timestamp'] if feature_buffer else None,
                'newest_record': feature_buffer[-1]['timestamp'] if feature_buffer else None,
            }

        # Overall health
        statuses = []
        for report in reports.values():
            statuses.append(report['input_drift'].get('status', 'UNKNOWN'))
            statuses.append(report['prediction_drift'].get('status', 'UNKNOWN'))

        if 'CRITICAL' in statuses:
            overall_health = 'CRITICAL'
        elif 'WARNING' in statuses:
            overall_health = 'WARNING'
        elif all(s in ('OK', 'INSUFFICIENT_DATA') for s in statuses):
            overall_health = 'OK'
        else:
            overall_health = 'UNKNOWN'

        return {
            'overall_health': overall_health,
            'models': reports,
            'generated_at': datetime.now().isoformat(),
            'thresholds': {
                'psi_warning': PSI_THRESHOLD_WARNING,
                'psi_critical': PSI_THRESHOLD_CRITICAL,
            },
        }


def is_model_healthy(model_name: str) -> bool:
    """
    Quick health check for governance gate.

    Returns True if the model has no critical drift.
    Can be called from governance decorators to gate predictions.
    """
    monitor = ModelMonitor()
    input_drift = monitor.check_input_drift(model_name)
    pred_drift = monitor.check_prediction_drift(model_name)

    # Block only on CRITICAL drift
    if input_drift.get('status') == 'CRITICAL':
        logger.warning(f"Model {model_name} has CRITICAL input drift — blocking predictions")
        return False
    if pred_drift.get('status') == 'CRITICAL':
        logger.warning(f"Model {model_name} has CRITICAL prediction drift — blocking predictions")
        return False

    return True


# Singleton
_monitor: Optional[ModelMonitor] = None


def get_model_monitor() -> ModelMonitor:
    """Get or create the model monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = ModelMonitor()
    return _monitor
