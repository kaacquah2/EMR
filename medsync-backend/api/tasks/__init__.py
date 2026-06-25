"""
Async/background tasks for MedSync EMR.

- export_tasks: PDF export operations
- appointment_tasks: No-show management (run via management command or sync fallback)
- pharmacy_tasks: Stock expiry checks
- fallback: Graceful fallback to synchronous execution when broker unavailable
"""
from .export_tasks import export_patient_pdf_task, export_encounter_pdf_task
from .appointment_tasks import mark_no_shows_task
from .fallback import can_use_celery, execute_task_sync_or_async

__all__ = [
    "export_patient_pdf_task",
    "export_encounter_pdf_task",
    "mark_no_shows_task",
    "can_use_celery",
    "execute_task_sync_or_async",
]
