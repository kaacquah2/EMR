"""
Interop consent: grant, list, revoke. Used by consent views (HTTP adapters only).
"""

from __future__ import annotations

from typing import Any, Tuple, Union

from django.utils.dateparse import parse_datetime

from core.models import Hospital
from interop.models import Consent, FacilityPatient, GlobalPatient

from api.utils import get_effective_hospital, get_global_patient_queryset, get_request_hospital

from .audit_service import log_event

ErrorTuple = Tuple[str, int]
GrantOk = Tuple[Consent, None]
GrantErr = Tuple[None, ErrorTuple]
ListOk = Tuple[Any, None]
ListErr = Tuple[None, ErrorTuple]
RevokeOk = Tuple[Consent, None]
RevokeErr = Tuple[None, ErrorTuple]


def interop_role_ok(user) -> bool:
    return user.role in ("doctor", "hospital_admin", "super_admin")


def grant_consent(request, payload: dict[str, Any]) -> Union[GrantOk, GrantErr]:
    """Create consent if authorized. Returns (consent, None) or (None, (message, http_status))."""
    user = request.user
    if not interop_role_ok(user):
        return None, ("Permission denied", 403)

    global_patient_id = payload.get("global_patient_id")
    granted_to_facility_id = payload.get("granted_to_facility_id")
    scope = payload.get("scope")
    expires_at = payload.get("expires_at")

    if not global_patient_id or not granted_to_facility_id or not scope:
        return None, (
            "global_patient_id, granted_to_facility_id, and scope required",
            400,
        )
    if scope not in (Consent.SCOPE_SUMMARY, Consent.SCOPE_FULL_RECORD):
        return None, ("scope must be SUMMARY or FULL_RECORD", 400)

    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return None, ("Global patient not found", 404)

    if user.role != "super_admin":
        req_h = get_request_hospital(request)
        if not req_h:
            return None, ("No facility assigned", 400)
        if not FacilityPatient.objects.filter(
            global_patient=gp,
            facility=req_h,
            deleted_at__isnull=True,
        ).exists():
            return None, (
                "Only the facility that has this patient linked can grant consent",
                403,
            )

    try:
        to_facility = Hospital.objects.get(id=granted_to_facility_id)
    except (Hospital.DoesNotExist, ValueError):
        return None, ("Facility not found", 404)

    exp = None
    if expires_at:
        try:
            exp = parse_datetime(expires_at)
        except Exception:
            exp = None

    consent = Consent.objects.create(
        global_patient=gp,
        granted_to_facility=to_facility,
        granted_by=user,
        scope=scope,
        expires_at=exp,
        is_active=True,
    )
    log_event(
        user,
        "CREATE",
        resource_type="consent",
        resource_id=consent.id,
        hospital=get_request_hospital(request),
        request=request,
        extra_data={
            "global_patient_id": str(gp.id),
            "granted_to_facility_id": str(to_facility.id),
            "scope": scope,
        },
    )
    return consent, None


def consents_for_global_patient(
    request,
    global_patient_id: str,
) -> Union[ListOk, ListErr]:
    """Return Consent queryset for audit list, or error tuple."""
    if not interop_role_ok(request.user):
        return None, ("Permission denied", 403)
    if not global_patient_id:
        return None, ("global_patient_id required", 400)

    qs = get_global_patient_queryset(
        request.user,
        get_effective_hospital(request),
    ).filter(id=global_patient_id)
    if not qs.exists():
        return None, ("Global patient not found", 404)
    gp = qs.first()
    consents = (
        Consent.objects.filter(global_patient=gp)
        .select_related("granted_to_facility", "granted_by")
        .order_by("-created_at")
    )
    return consents, None


def revoke_consent(request, pk: str) -> Union[RevokeOk, RevokeErr]:
    """Deactivate consent if authorized. Returns (consent, None) or (None, (message, status))."""
    if not interop_role_ok(request.user):
        return None, ("Permission denied", 403)
    try:
        consent = Consent.objects.select_related(
            "global_patient",
            "granted_to_facility",
            "granted_by",
        ).get(id=pk)
    except (Consent.DoesNotExist, ValueError):
        return None, ("Consent not found", 404)

    if request.user.role != "super_admin":
        req_h = get_request_hospital(request)
        if not req_h or consent.granted_by.hospital_id != req_h.id:
            return None, (
                "Only the facility that granted this consent can revoke it",
                403,
            )

    if not consent.is_active:
        return consent, None

    consent.is_active = False
    consent.save(update_fields=["is_active"])
    log_event(
        request.user,
        "CROSS_FACILITY_ACCESS_REVOKED",
        resource_type="consent",
        resource_id=consent.id,
        hospital=get_request_hospital(request),
        request=request,
        extra_data={
            "global_patient_id": str(consent.global_patient_id),
            "granted_to_facility_id": str(consent.granted_to_facility_id),
        },
    )
    return consent, None
