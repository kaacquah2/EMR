import csv
import json
from datetime import timedelta
from io import StringIO
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from patients.models import Invoice
from core.models import AuditLog
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_patients_csv(request):
    """Export patient list as CSV. Admin, Doctor (facility-scoped)."""
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = get_patient_queryset(request.user, get_effective_hospital(request)).order_by("full_name")[:5000]
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow([
        "patient_id", "ghana_health_id", "full_name", "date_of_birth", "gender",
        "blood_group", "phone", "national_id", "registered_at_name"
    ])
    for p in qs:
        w.writerow([
            str(p.id),
            p.ghana_health_id,
            p.full_name,
            p.date_of_birth.isoformat() if p.date_of_birth else "",
            p.gender,
            p.blood_group,
            p.phone or "",
            p.national_id or "",
            p.registered_at.name if p.registered_at_id else "",
        ])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="patients_export.csv"'
    return resp


def _audit_export_days(request):
    if request.method == "POST" and getattr(request, "data", None):
        raw = request.data.get("days", 90)
    else:
        raw = request.GET.get("days", 90)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 90
    return max(1, min(days, 3650))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def export_audit_csv(request):
    """Export audit logs as CSV. Admin only. Optional days= (default 90)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    days = _audit_export_days(request)
    cutoff = timezone.now() - timedelta(days=days)
    qs = AuditLog.objects.all().select_related("user", "hospital").filter(timestamp__gte=cutoff)
    req_hospital = get_request_hospital(request)
    if req_hospital:
        qs = qs.filter(hospital=req_hospital)
    qs = qs.order_by("-timestamp")[:5000]
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "user", "action", "resource_type", "resource_id", "hospital", "ip_address", "extra_data"])
    row_count = 0
    for log in qs:
        extra = ""
        if log.extra_data:
            extra = json.dumps(log.extra_data)
        w.writerow([
            log.timestamp.isoformat() if log.timestamp else "",
            log.user.full_name if log.user_id else "",
            log.action,
            log.resource_type or "",
            str(log.resource_id) if log.resource_id else "",
            log.hospital.name if log.hospital_id else "",
            str(log.ip_address) if log.ip_address else "",
            extra,
        ])
        row_count += 1
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="audit_logs_export.csv"'
    resp["X-Export-Count"] = str(row_count)
    return resp


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def invoice_list_create(request):
    """List or create invoices (minimal billing). Hospital-scoped."""
    if request.user.role not in ("super_admin", "hospital_admin", "billing_staff"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "hospital_admin" and not hospital:
        return Response({"data": []})
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        from core.models import Hospital
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except Hospital.DoesNotExist:
            return Response({"data": []})
    if request.method == "GET":
        qs = Invoice.objects.filter(hospital=hospital).select_related(
            "patient", "created_by").order_by("-created_at")[:100]
        if request.GET.get("patient_id"):
            qs = qs.filter(patient_id=request.GET.get("patient_id"))
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET.get("status"))
        data = [
            {
                "id": str(inv.id),
                "patient_id": str(inv.patient_id),
                "patient_name": inv.patient.full_name,
                "amount_cents": inv.amount_cents,
                "currency": inv.currency,
                "status": inv.status,
                "notes": inv.notes,
                "created_at": inv.created_at.isoformat(),
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "payment_method": getattr(inv, "payment_method", "cash"),
                "paid_amount": float(inv.paid_amount) if hasattr(inv, "paid_amount") and inv.paid_amount is not None else 0.0,
                "nhis_claim_status": getattr(inv, "nhis_claim_status", None),
                "nhis_claim_reference": getattr(inv, "nhis_claim_reference", None),
            }
            for inv in qs
        ]
        return Response({"data": data})
    if request.method == "POST":
        if request.user.role != "billing_staff":
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not hospital:
            return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
        patient_id = request.data.get("patient_id")
        if not patient_id:
            return Response({"message": "patient_id required"}, status=status.HTTP_400_BAD_REQUEST)
        patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
        if not patient or patient.registered_at_id != hospital.id:
            return Response({"message": "Patient not found or not at this hospital"}, status=status.HTTP_404_NOT_FOUND)
        amount_cents = int(request.data.get("amount_cents") or 0)
        inv = Invoice.objects.create(
            patient=patient, hospital=hospital, amount_cents=amount_cents, currency=(
                request.data.get("currency") or "GHS").strip()[
                :3], status=request.data.get("status") if request.data.get("status") in (
                "draft", "issued", "paid", "partial", "cancelled") else "draft", notes=(
                    request.data.get("notes") or "").strip() or None, created_by=request.user, )
        return Response({"id": str(inv.id),
                         "patient_id": str(inv.patient_id),
                         "amount_cents": inv.amount_cents,
                         "status": inv.status},
                        status=status.HTTP_201_CREATED,
                        )
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nhis_claim_submit(request):
    """
    Submit an NHIS claim by patient or encounter.
    Finds the latest issued/partial NHIS invoice for the patient and submits it
    to the Ghana NHIA API (or mock fallback when NHIS_API_KEY is not configured).

    Request body:
      patient_id: str  (required if encounter_id omitted)
      encounter_id: str  (optional — used to identify the patient)
      nhis_member_id: str  (required — patient NHIS card number)
      diagnosis_codes: list[str]  (required — ICD-10 codes, e.g. ["A09"])
    """
    from api.integrations.nhis_client import (
        get_nhis_client, NHISClaimItem,
        NHISRetryableError, NHISClaimError, NHISCircuitOpenError,
    )
    from decimal import Decimal

    if request.user.role not in ("hospital_admin", "billing_staff"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"message": "No hospital assigned"}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve patient from encounter_id or patient_id
    encounter_id = request.data.get("encounter_id")
    patient_id = request.data.get("patient_id")
    nhis_member_id = (request.data.get("nhis_member_id") or "").strip()
    diagnosis_codes = request.data.get("diagnosis_codes") or []

    if not encounter_id and not patient_id:
        return Response({"message": "encounter_id or patient_id required"}, status=status.HTTP_400_BAD_REQUEST)
    if not nhis_member_id:
        return Response({"message": "nhis_member_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(diagnosis_codes, list) or not diagnosis_codes:
        return Response({"message": "diagnosis_codes must be a non-empty list of ICD-10 codes"}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve patient_id from encounter if needed
    if encounter_id and not patient_id:
        from records.models import Encounter
        enc = Encounter.objects.filter(id=encounter_id, hospital=hospital).first()
        if not enc:
            return Response({"message": "Encounter not found"}, status=status.HTTP_404_NOT_FOUND)
        patient_id = str(enc.patient_id)

    # Find the latest NHIS invoice that hasn't been claimed yet
    invoice = (
        Invoice.objects.filter(
            hospital=hospital,
            patient_id=patient_id,
            payment_method="nhis",
        )
        .exclude(nhis_claim_status__in=["submitted", "approved"])
        .order_by("-created_at")
        .first()
    )
    if not invoice:
        return Response(
            {"message": "No unclaimed NHIS invoice found for this patient. Create an invoice with payment_method=nhis first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    nhis_client = get_nhis_client()

    # Build claim items from invoice line items
    claim_items = []
    for item in invoice.items.all():
        claim_items.append(NHISClaimItem(
            service_code=getattr(item, "service_type", None) or "CONSULT",
            description=item.description,
            quantity=item.quantity,
            unit_price_ghs=Decimal(str(item.unit_price)) / 100,
        ))
    if not claim_items:
        claim_items.append(NHISClaimItem(
            service_code="CONSULT",
            description="Medical Services",
            quantity=1,
            unit_price_ghs=invoice.total_amount,
        ))

    try:
        result = nhis_client.submit_claim(
            invoice_id=str(invoice.id),
            nhis_member_id=nhis_member_id,
            diagnosis_codes=diagnosis_codes,
            items=claim_items,
        )

        invoice.nhis_claim_status = "submitted"
        invoice.nhis_claim_reference = result.claim_reference
        if hasattr(invoice, "nhis_submitted_at"):
            from django.utils import timezone as _tz
            invoice.nhis_submitted_at = _tz.now()
        invoice.save(update_fields=[
            "nhis_claim_status", "nhis_claim_reference",
            *(["nhis_submitted_at"] if hasattr(invoice, "nhis_submitted_at") else []),
        ])

        return Response(
            {
                "claim_ref": result.claim_reference,
                "nhis_status": result.status,
                "invoice_id": str(invoice.id),
                "message": "NHIS claim submitted. Allow 24–48 hours for NHIA processing.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    except NHISCircuitOpenError:
        return Response(
            {"message": "NHIS API temporarily unavailable. Please retry shortly."},
            status=status.HTTP_202_ACCEPTED,
        )
    except NHISRetryableError as exc:
        return Response({"message": f"NHIS service error: {exc}. Please retry."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except NHISClaimError as exc:
        return Response({"message": f"NHIS rejected claim: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
