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
