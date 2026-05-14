"""
Celery tasks for AI model monitoring.

Periodic tasks:
- check_model_drift: Hourly check for input/prediction drift
- generate_monitoring_report: Daily comprehensive report
"""

import logging
from typing import Dict, Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ai.check_model_drift', bind=True, max_retries=1)
def check_model_drift(self) -> Dict[str, Any]:
    """
    Periodic task: Check all models for drift.

    Runs hourly via django-celery-beat. Logs warnings to AuditLog
    when drift exceeds thresholds.

    Schedule (add to CELERY_BEAT_SCHEDULE):
        'check-model-drift': {
            'task': 'ai.check_model_drift',
            'schedule': crontab(minute=0),  # Every hour
        }
    """
    try:
        from api.ai.model_monitor import get_model_monitor

        monitor = get_model_monitor()
        report = monitor.get_monitoring_report()

        # Log drift alerts
        _log_drift_alerts(report)

        logger.info(
            f"Model drift check complete. Overall health: {report['overall_health']}"
        )
        return {
            'status': 'success',
            'overall_health': report['overall_health'],
            'models_checked': len(report.get('models', {})),
        }

    except Exception as e:
        logger.error(f"Model drift check failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='ai.generate_monitoring_report', bind=True, max_retries=1)
def generate_monitoring_report(self) -> Dict[str, Any]:
    """
    Periodic task: Generate comprehensive monitoring report.

    Runs daily. Stores full report in cache and logs summary.

    Schedule (add to CELERY_BEAT_SCHEDULE):
        'generate-monitoring-report': {
            'task': 'ai.generate_monitoring_report',
            'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
        }
    """
    try:
        from api.ai.model_monitor import get_model_monitor
        from django.core.cache import cache

        monitor = get_model_monitor()
        report = monitor.get_monitoring_report()

        # Store full report in cache (24h TTL)
        cache.set('ai_monitoring_report_latest', report, 60 * 60 * 24)

        # Log summary
        for model_name, model_report in report.get('models', {}).items():
            input_status = model_report['input_drift'].get('status', 'UNKNOWN')
            pred_status = model_report['prediction_drift'].get('status', 'UNKNOWN')
            n_preds = model_report.get('predictions_recorded', 0)
            logger.info(
                f"Model {model_name}: input_drift={input_status}, "
                f"pred_drift={pred_status}, predictions={n_preds}"
            )

        logger.info(
            f"Monitoring report generated. Overall: {report['overall_health']}"
        )
        return {
            'status': 'success',
            'overall_health': report['overall_health'],
        }

    except Exception as e:
        logger.error(f"Monitoring report generation failed: {e}")
        return {'status': 'error', 'error': str(e)}


def _log_drift_alerts(report: Dict[str, Any]) -> None:
    """Log drift alerts to AuditLog for governance tracking."""
    try:
        from core.models import AuditLog

        for model_name, model_report in report.get('models', {}).items():
            for drift_type in ('input_drift', 'prediction_drift'):
                drift_data = model_report.get(drift_type, {})
                status = drift_data.get('status', 'UNKNOWN')

                if status in ('WARNING', 'CRITICAL'):
                    AuditLog.objects.create(
                        user=None,
                        action=f'AI_DRIFT_{status}',
                        resource_type='ModelMonitoring',
                        resource_id=model_name,
                        hospital=None,
                        ip_address='system',
                        extra_data={
                            'drift_type': drift_type,
                            'status': status,
                            'max_psi': drift_data.get('max_psi'),
                            'message': drift_data.get('message'),
                            'action_recommended': drift_data.get('action'),
                            'checked_at': drift_data.get('checked_at'),
                        },
                    )
                    logger.warning(
                        f"DRIFT ALERT [{status}]: {model_name} — "
                        f"{drift_type} PSI={drift_data.get('max_psi', '?')}"
                    )

    except Exception as e:
        logger.error(f"Failed to log drift alerts: {e}")
