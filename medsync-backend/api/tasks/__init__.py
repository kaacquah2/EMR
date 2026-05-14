"""
Celery tasks for MedSync EMR.

This module contains all async task definitions:
- export_tasks: PDF export operations
- ai_tasks: AI analysis and predictions
- appointment_tasks: Appointment and no-show management
- fallback: Graceful fallback to synchronous execution when broker unavailable
"""
from .export_tasks import export_patient_pdf_task, export_encounter_pdf_task
from .ai_tasks import comprehensive_analysis_task, risk_prediction_task, rebuild_faiss_index
from .appointment_tasks import mark_no_shows_task, send_no_show_notification_task
from .fallback import can_use_celery, execute_task_sync_or_async

__all__ = [
    "export_patient_pdf_task",
    "export_encounter_pdf_task",
    "comprehensive_analysis_task",
    "risk_prediction_task",
    "rebuild_faiss_index",
    "mark_no_shows_task",
    "send_no_show_notification_task",
    "can_use_celery",
    "execute_task_sync_or_async",
]
