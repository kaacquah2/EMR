"""
Clinical event notifications — WSGI/polling mode.

The app runs under Gunicorn (WSGI) without Django Channels.  Real-time push via
WebSocket is not available; clients poll the relevant REST endpoints for updates
(alerts, lab results, admissions, prescriptions).

The functions below emit structured log lines (picked up by the JSON logger /
Sentry) so that operators still get observability for clinical events.  When a
real-time layer is added in the future, these functions can be updated to also
push to a channel layer or message broker without changing call sites.

Signal receivers are retained so that saving a LabResult / LabOrder /
Prescription / PatientAdmission triggers a log entry automatically.
"""

import logging

logger = logging.getLogger("medsync.alerts")


# ---------------------------------------------------------------------------
# Notification helpers — currently log-only; upgrade to push when a channel
# layer is available.
# ---------------------------------------------------------------------------

def broadcast_alert_created(alert):
    """Log that a new clinical alert was created."""
    logger.info(
        "alert.created hospital=%s patient=%s severity=%s id=%s",
        alert.hospital_id,
        alert.patient_id,
        alert.severity,
        alert.id,
    )


def broadcast_alert_resolved(alert):
    """Log that a clinical alert was resolved."""
    logger.info(
        "alert.resolved hospital=%s id=%s status=%s",
        alert.hospital_id,
        alert.id,
        alert.status,
    )


def broadcast_stock_alert(stock_alert):
    """Log a pharmacy stock alert (low-stock or expiring)."""
    logger.info(
        "stock_alert.%s hospital=%s drug=%s id=%s",
        stock_alert.alert_type,
        stock_alert.hospital_id,
        stock_alert.drug_stock.drug_name if stock_alert.drug_stock_id else "unknown",
        stock_alert.id,
    )


def broadcast_lab_result(lab_result):
    """Log a lab result update."""
    try:
        hospital_id = lab_result.record.hospital_id
    except Exception:
        hospital_id = None
    logger.info(
        "lab.result_updated hospital=%s patient=%s test=%s status=%s id=%s",
        hospital_id,
        getattr(lab_result.record, "patient_id", None),
        lab_result.test_name,
        lab_result.status,
        lab_result.id,
    )


def broadcast_admission(admission):
    """Log a patient admission or discharge event."""
    status = "admitted" if not admission.discharged_at else "discharged"
    logger.info(
        "admission.%s hospital=%s patient=%s ward=%s id=%s",
        status,
        admission.hospital_id,
        admission.patient_id,
        admission.ward_id,
        admission.id,
    )


def broadcast_password_override(hospital_id, payload):
    """Log a super-admin password override notification."""
    logger.warning(
        "security.password_override hospital=%s performed_by=%s",
        hospital_id,
        payload.get("performed_by"),
    )


# ---------------------------------------------------------------------------
# Signal receivers
# ---------------------------------------------------------------------------
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="records.LabResult")
def on_lab_result_save(sender, instance, created, **kwargs):
    broadcast_lab_result(instance)


@receiver(post_save, sender="records.LabOrder")
def on_lab_order_save(sender, instance, created, **kwargs):
    logger.info(
        "lab.order_updated hospital=%s status=%s id=%s",
        instance.hospital_id,
        instance.status,
        instance.id,
    )


@receiver(post_save, sender="records.Prescription")
def on_prescription_save(sender, instance, created, **kwargs):
    logger.info(
        "pharmacy.prescription_updated hospital=%s status=%s id=%s",
        instance.hospital_id,
        instance.status,
        instance.id,
    )


@receiver(post_save, sender="patients.PatientAdmission")
def on_admission_save(sender, instance, created, **kwargs):
    broadcast_admission(instance)
