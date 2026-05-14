"""
Broadcast clinical alert events over Django Channels.
Call broadcast_alert_created / broadcast_alert_resolved from views (sync context).
"""
from asgiref.sync import async_to_sync
from django.conf import settings


def _channel_layer():
    if not getattr(settings, "CHANNEL_LAYERS", None):
        return None
    from channels.layers import get_channel_layer
    return get_channel_layer()


def broadcast_alert_created(alert):
    """Notify WebSocket clients that a new alert was created for the hospital."""
    layer = _channel_layer()
    if not layer:
        return
    group = f"alerts_{alert.hospital_id}"
    payload = {
        "type": "alert_created",
        "id": str(alert.id),
        "patient_id": str(alert.patient_id),
        "hospital_id": str(alert.hospital_id),
        "severity": alert.severity,
        "message": alert.message,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
    }
    async_to_sync(layer.group_send)(group, {"type": "alert_event", "payload": payload})


def broadcast_alert_resolved(alert):
    """Notify WebSocket clients that an alert was resolved."""
    layer = _channel_layer()
    if not layer:
        return
    group = f"alerts_{alert.hospital_id}"
    payload = {
        "type": "alert_resolved",
        "id": str(alert.id),
        "hospital_id": str(alert.hospital_id),
        "status": alert.status,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }
    async_to_sync(layer.group_send)(group, {"type": "alert_event", "payload": payload})


def broadcast_stock_alert(stock_alert):
    """
    Notify WebSocket clients of a stock alert (low-stock or expiring).
    
    Broadcasts to hospital-specific group using existing AlertConsumer infrastructure.
    """
    layer = _channel_layer()
    if not layer:
        return
    
    group = f"alerts_{stock_alert.hospital_id}"
    payload = {
        "type": "stock_alert",
        "id": str(stock_alert.id),
        "hospital_id": str(stock_alert.hospital_id),
        "drug_name": stock_alert.drug_stock.drug_name,
        "batch_number": stock_alert.drug_stock.batch_number,
        "alert_type": stock_alert.alert_type,
        "severity": stock_alert.severity,
        "message": stock_alert.message,
        "status": stock_alert.status,
        "created_at": stock_alert.created_at.isoformat(),
    }
    async_to_sync(layer.group_send)(group, {"type": "alert_event", "payload": payload})


def broadcast_lab_result(lab_result):
    """Notify WebSocket clients of lab result updates."""
    layer = _channel_layer()
    if not layer:
        return
    hospital_id = lab_result.record.hospital_id
    group = f"alerts_{hospital_id}"
    payload = {
        "type": "lab_event",
        "id": str(lab_result.id),
        "patient_id": str(lab_result.record.patient_id),
        "hospital_id": str(hospital_id),
        "test_name": lab_result.test_name,
        "status": lab_result.status,
        "result_date": lab_result.result_date.isoformat() if lab_result.result_date else None,
    }
    async_to_sync(layer.group_send)(group, {"type": "lab_event", "payload": payload})


def broadcast_admission(admission):
    """Notify WebSocket clients of patient admission events."""
    layer = _channel_layer()
    if not layer:
        return
    hospital_id = admission.hospital_id
    group = f"alerts_{hospital_id}"
    payload = {
        "type": "admission_event",
        "id": str(admission.id),
        "patient_id": str(admission.patient_id),
        "hospital_id": str(hospital_id),
        "ward_id": str(admission.ward_id) if admission.ward_id else None,
        "status": "admitted" if not admission.discharged_at else "discharged",
        "admitted_at": admission.admitted_at.isoformat() if admission.admitted_at else None,
        "discharged_at": admission.discharged_at.isoformat() if admission.discharged_at else None,
    }
    async_to_sync(layer.group_send)(group, {"type": "admission_event", "payload": payload})


def broadcast_password_override(hospital_id, payload):
    """Notify WebSocket clients in the hospital_admin group of a password override."""
    layer = _channel_layer()
    if not layer:
        return
    group = f"hospital_admin_{hospital_id}"
    async_to_sync(layer.group_send)(group, {"type": "security_event", "payload": payload})


# Signal receivers
from django.db.models.signals import post_save
from django.dispatch import receiver

# Imports are inside receivers or at the end to prevent circular imports during app startup
@receiver(post_save, sender="records.LabResult")
def on_lab_result_save(sender, instance, created, **kwargs):
    # Broadcast on creation or any status change
    broadcast_lab_result(instance)

@receiver(post_save, sender="records.LabOrder")
def on_lab_order_save(sender, instance, created, **kwargs):
    """Notify lab tech of new or updated orders."""
    layer = _channel_layer()
    if not layer:
        return
    group = f"alerts_{instance.hospital_id}"
    payload = {
        "type": "lab_event",
        "subtype": "order_updated",
        "id": str(instance.id),
        "hospital_id": str(instance.hospital_id),
        "status": instance.status,
    }
    async_to_sync(layer.group_send)(group, {"type": "lab_event", "payload": payload})

@receiver(post_save, sender="records.Prescription")
def on_prescription_save(sender, instance, created, **kwargs):
    """Notify pharmacy tech of new or updated prescriptions."""
    layer = _channel_layer()
    if not layer:
        return
    group = f"alerts_{instance.hospital_id}"
    payload = {
        "type": "pharmacy_event",
        "subtype": "prescription_updated",
        "id": str(instance.id),
        "hospital_id": str(instance.hospital_id),
        "status": instance.status,
    }
    async_to_sync(layer.group_send)(group, {"type": "alert_event", "payload": payload})

@receiver(post_save, sender="patients.PatientAdmission")
def on_admission_save(sender, instance, created, **kwargs):
    broadcast_admission(instance)
