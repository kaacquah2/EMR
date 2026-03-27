"""
Optional outbound integration hooks (pharmacy, PACS).
Fire-and-forget POST to configured URLs; does not block request.
"""
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)
WEBHOOK_TIMEOUT_SEC = 2


def _post_json(url, payload):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SEC) as resp:
            return resp.status in (200, 201, 202, 204)
    except Exception as e:
        logger.warning("Integration webhook POST failed: %s", e)
        return False


def notify_pharmacy_dispense(record_id, prescription_id, dispense_status, hospital_id=None):
    """If PHARMACY_WEBHOOK_URL is set, POST dispense event (no PHI)."""
    from django.conf import settings
    url = getattr(settings, "PHARMACY_WEBHOOK_URL", "") or ""
    if not url:
        return
    payload = {
        "event": "prescription_dispense",
        "record_id": str(record_id),
        "prescription_id": str(prescription_id),
        "dispense_status": dispense_status,
        "hospital_id": str(hospital_id) if hospital_id else None,
    }
    _post_json(url, payload)


def notify_pacs_result(order_id, attachment_url, status, hospital_id=None):
    """If PACS_CALLBACK_URL is set, POST radiology result event (no PHI)."""
    from django.conf import settings
    url = getattr(settings, "PACS_CALLBACK_URL", "") or ""
    if not url:
        return
    payload = {
        "event": "radiology_result",
        "order_id": str(order_id),
        "attachment_url": attachment_url,
        "status": status,
        "hospital_id": str(hospital_id) if hospital_id else None,
    }
    _post_json(url, payload)
