import os
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.utils import (
    audit_log,
    get_effective_hospital,
    get_lab_order_queryset,
)
from patients.models import ClinicalAlert
from records.models import LabOrder, LabResult

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_ATTACHMENT_CONTENT_TYPE = "application/pdf"
PDF_MAGIC = b"%PDF"
TAT_TARGETS = {"stat": 60, "urgent": 240, "routine": 1440}
URGENCY_RANK = {"stat": 1, "urgent": 2, "routine": 3}
PENDING_STATUSES = {"ordered", "collected", "in_progress"}
RESULTABLE_STATUSES = {"in_progress"}


def _patient_age(date_of_birth):
    if not date_of_birth:
        return None
    today = timezone.now().date()
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def _critical_threshold_for_test(test_name):
    table = getattr(settings, "LAB_CRITICAL_THRESHOLDS", {}) or {}
    key = (test_name or "").strip().lower()
    if key in table:
        return table[key]
    return None


def _parse_numeric_result(result_value):
    if result_value is None:
        return None
    token = str(result_value).strip().split(" ")[0]
    try:
        return Decimal(token)
    except (InvalidOperation, ValueError):
        return None


def _is_critical_value(test_name, result_value):
    threshold = _critical_threshold_for_test(test_name)
    if not threshold:
        return False, None
    numeric = _parse_numeric_result(result_value)
    if numeric is None:
        return False, None
    low = threshold.get("low")
    high = threshold.get("high")
    if low is not None and numeric < Decimal(str(low)):
        return True, f"critical low (< {low})"
    if high is not None and numeric > Decimal(str(high)):
        return True, f"critical high (> {high})"
    return False, None


def _tat_snapshot(order):
    ordered_at = order.record.created_at if order.record else None
    if not ordered_at:
        return {"tat_target_minutes": TAT_TARGETS.get(order.urgency, 1440), "minutes_remaining": None}
    elapsed = int((timezone.now() - ordered_at).total_seconds() / 60)
    target = TAT_TARGETS.get(order.urgency, 1440)
    return {"tat_target_minutes": target, "minutes_remaining": target - elapsed}


def _lab_order_payload(order):
    p = order.record.patient if order.record else None
    tat = _tat_snapshot(order)
    return {
        "id": str(order.id),
        "patient_name": p.full_name if p else "",
        "patient_age": _patient_age(getattr(p, "date_of_birth", None)),
        "patient_gender": getattr(p, "gender", None),
        "gha_id": p.ghana_health_id if p else "",
        "test_name": order.test_name,
        "urgency": order.urgency,
        "urgency_rank": URGENCY_RANK.get(order.urgency, 99),
        "status": order.status,
        "ordered_at": order.record.created_at.isoformat() if order.record else None,
        "collection_time": order.collection_time.isoformat() if order.collection_time else None,
        "lab_unit_id": str(order.lab_unit_id) if order.lab_unit_id else None,
        "ordering_doctor_name": order.record.created_by.full_name if order.record and order.record.created_by else "",
        "tat_target_minutes": tat["tat_target_minutes"],
        "minutes_remaining": tat["minutes_remaining"],
    }


def _status_tab_filter(qs, tab):
    tab_value = (tab or "all").strip().lower()
    if tab_value in ("pending",):
        return qs.filter(status__in=["ordered", "collected"]), tab_value
    if tab_value in ("in_progress",):
        return qs.filter(status="in_progress"), tab_value
    if tab_value in ("resulted_today", "resulted"):
        return qs.filter(status="resulted", resulted_at__date=timezone.now().date()), "resulted_today"
    if tab_value == "verified":
        return qs.filter(status="verified"), tab_value
    return qs, "all"


def _validate_attachment_url(url, content_type=None, size_bytes=None):
    """Validate lab result attachment: PDF only, max 10MB. Returns (ok, error_message)."""
    if not url or not isinstance(url, str):
        return True, None
    url = url.strip()
    if not url:
        return True, None
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        if not path.endswith(".pdf"):
            return False, "Attachment must be a PDF (URL path must end with .pdf)."
    except Exception:
        return False, "Invalid attachment URL."
    if content_type is not None and str(content_type).strip().lower() != ALLOWED_ATTACHMENT_CONTENT_TYPE:
        return False, "Attachment must be PDF only (content type application/pdf)."
    if size_bytes is not None:
        try:
            size = int(size_bytes)
            if size < 0 or size > MAX_ATTACHMENT_SIZE_BYTES:
                return False, "Attachment must be at most 10MB."
        except (TypeError, ValueError):
            return False, "Invalid attachment size."
    return True, None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lab_attachment_upload(request):
    """Accept a PDF file (max 10MB), store under MEDIA_ROOT/lab_attachments, return URL."""
    if request.user.role != "lab_technician":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    file = request.FILES.get("file")
    if not file:
        return Response(
            {"message": "No file provided. Use multipart form key 'file'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    content_type = (getattr(file, "content_type") or "").strip().lower()
    if content_type != ALLOWED_ATTACHMENT_CONTENT_TYPE:
        return Response(
            {"message": "Attachment must be PDF only (content type application/pdf)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if file.size > MAX_ATTACHMENT_SIZE_BYTES or file.size < 0:
        return Response(
            {"message": "Attachment must be at most 10MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    head = file.read(4)
    file.seek(0)
    if head != PDF_MAGIC:
        return Response(
            {"message": "File is not a valid PDF."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    subdir = os.path.join(settings.MEDIA_ROOT, "lab_attachments")
    os.makedirs(subdir, exist_ok=True)
    name = f"{uuid.uuid4()}.pdf"
    path = os.path.join(subdir, name)
    with open(path, "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
    relative_url = f"{settings.MEDIA_URL.rstrip('/')}/lab_attachments/{name}"
    absolute_url = request.build_absolute_uri(relative_url)
    return Response({
        "url": absolute_url,
        "attachment_content_type": ALLOWED_ATTACHMENT_CONTENT_TYPE,
        "attachment_size_bytes": file.size,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lab_orders_list(request):
    if request.user.role != "lab_technician":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    tab = request.GET.get("tab", "all")
    limit = min(int(request.GET.get("limit", "100") or "100"), 500)
    offset = int(request.GET.get("offset", "0") or "0")
    hospital = get_effective_hospital(request)
    patient_search = (request.GET.get("patient_search") or request.GET.get("search") or "").strip()
    urgency = (request.GET.get("urgency") or "").strip().lower()

    orders = (
        get_lab_order_queryset(request.user, hospital)
        .select_related("record", "record__patient", "record__created_by", "lab_unit")
        .annotate(
            urgency_rank=Case(
                When(urgency="stat", then=1),
                When(urgency="urgent", then=2),
                default=3,
                output_field=IntegerField(),
            )
        )
    )

    if patient_search:
        orders = orders.filter(
            Q(record__patient__full_name__icontains=patient_search)
            | Q(record__patient__ghana_health_id__icontains=patient_search)
        )
    if urgency in {"stat", "urgent", "routine"}:
        orders = orders.filter(urgency=urgency)

    orders, normalized_tab = _status_tab_filter(orders, tab)
    orders = orders.order_by("urgency_rank", "record__created_at")
    total = orders.count()
    page = orders[offset : offset + limit]
    data = [_lab_order_payload(o) for o in page]

    stat_count = orders.filter(urgency="stat").count()
    urgent_count = orders.filter(urgency="urgent").count()
    routine_count = orders.filter(urgency="routine").count()
    in_progress_count = orders.filter(status="in_progress").count()

    return Response({
        "count": total,
        "limit": limit,
        "offset": offset,
        "tab": normalized_tab,
        "stats": {
            "stat_orders": stat_count,
            "urgent_orders": urgent_count,
            "routine_orders": routine_count,
            "in_progress_orders": in_progress_count,
        },
        "data": data,
    })


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def lab_order_detail(request, order_id):
    if request.user.role != "lab_technician":
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

    lab_order = (
        get_lab_order_queryset(request.user, get_effective_hospital(request))
        .filter(id=order_id)
        .select_related("record", "record__patient", "record__created_by", "lab_unit")
        .first()
    )
    if not lab_order:
        return Response({"message": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        payload = _lab_order_payload(lab_order)
        result = LabResult.objects.filter(lab_order=lab_order).first()
        payload["result"] = (
            {
                "result_value": result.result_value,
                "reference_range": result.reference_range,
                "attachment_url": result.attachment_url,
                "status": result.status,
                "result_date": result.result_date.isoformat() if result.result_date else None,
            }
            if result
            else None
        )
        return Response(payload)

    next_status = (request.data.get("status") or "").strip().lower()
    transition = {
        "ordered": {"collected"},
        "collected": {"in_progress"},
        "in_progress": set(),
        "resulted": {"verified"},
        "verified": set(),
    }
    if next_status not in {"collected", "in_progress", "verified"}:
        return Response({"message": "Unsupported status transition"}, status=status.HTTP_400_BAD_REQUEST)
    if next_status not in transition.get(lab_order.status, set()):
        return Response(
            {"message": f"Invalid transition from {lab_order.status} to {next_status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    update_fields = ["status", "assigned_to"]
    lab_order.status = next_status
    lab_order.assigned_to = request.user
    if next_status == "collected":
        lab_order.collection_time = now
        update_fields.append("collection_time")
    elif next_status == "in_progress":
        lab_order.started_at = now
        update_fields.append("started_at")
    elif next_status == "verified":
        lab_order.verified_at = now
        update_fields.append("verified_at")
        result = LabResult.objects.filter(lab_order=lab_order).first()
        if result:
            result.status = "verified"
            result.verified_by = request.user
            result.verified_at = now
            result.save(update_fields=["status", "verified_by", "verified_at"])
    lab_order.save(update_fields=update_fields)
    return Response(_lab_order_payload(lab_order))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lab_order_result(request, order_id):
    if request.user.role != "lab_technician":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    lab_order = (
        get_lab_order_queryset(request.user, get_effective_hospital(request))
        .filter(id=order_id)
        .select_related("record", "record__patient", "record__created_by")
        .first()
    )
    if not lab_order:
        return Response(
            {"message": "Order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if lab_order.status not in RESULTABLE_STATUSES:
        return Response(
            {"message": f"Order must be in_progress before posting result. Current status: {lab_order.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    lab_order.assigned_to = request.user
    lab_order.save(update_fields=["assigned_to"])
    data = request.data
    result_value = data.get("result_value")
    if not result_value:
        return Response({"message": "result_value is required"}, status=status.HTTP_400_BAD_REQUEST)
    critical, reason = _is_critical_value(lab_order.test_name, result_value)
    critical_notified = bool(data.get("critical_value_notified"))
    if critical and not critical_notified:
        return Response(
            {
                "message": "Critical value requires physician notification confirmation",
                "critical_value_required": True,
                "critical_reason": reason,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    lab_result, _ = LabResult.objects.get_or_create(
        lab_order=lab_order,
        defaults={
            "record": lab_order.record,
            "test_name": lab_order.test_name,
            "status": "pending",
            "lab_tech": request.user,
        },
    )
    lab_result.result_value = result_value
    lab_result.reference_range = data.get("reference_range")
    lab_result.status = "resulted"
    lab_result.lab_tech = request.user
    attachment_url = data.get("attachment_url")
    if attachment_url:
        ok, err = _validate_attachment_url(
            attachment_url,
            content_type=data.get("attachment_content_type"),
            size_bytes=data.get("attachment_size_bytes"),
        )
        if not ok:
            return Response({"message": err}, status=status.HTTP_400_BAD_REQUEST)
    lab_result.attachment_url = attachment_url or None
    lab_result.save()

    now = timezone.now()
    lab_order.status = "resulted"
    lab_order.resulted_at = now
    lab_order.save(update_fields=["status", "resulted_at"])

    if critical and critical_notified and lab_order.record and lab_order.record.patient:
        ClinicalAlert.objects.create(
            patient=lab_order.record.patient,
            hospital=lab_order.record.hospital,
            severity="critical",
            message=(
                f"Critical lab result for {lab_order.test_name}: {result_value}. "
                f"Ordering doctor: {lab_order.record.created_by.full_name if lab_order.record.created_by else 'Unknown'}"
            ),
            status="active",
            created_by=request.user,
            resource_type="lab_result",
            resource_id=lab_result.id,
        )
        audit_log(
            request.user,
            "UPDATE",
            "lab_result",
            str(lab_result.id),
            lab_order.record.hospital if lab_order.record else None,
            request,
            extra_data={"event": "CRITICAL_VALUE_NOTIFIED", "lab_order_id": str(lab_order.id)},
        )

    return Response(
        {
            "message": "Result submitted",
            "lab_result_id": str(lab_result.id),
            "status": lab_order.status,
            "critical_value_notified": critical and critical_notified,
        }
    )


# PHASE 6: Lab Technician Advanced Features

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lab_results_bulk_submit(request):
    if request.user.role != "lab_technician":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    results_data = request.data.get("results", [])
    if not results_data:
        return Response(
            {"message": "results array required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    hospital = get_effective_hospital(request)
    details = []
    submitted = 0
    failed = 0
    
    for item in results_data:
        order_id = item.get("order_id")
        if not order_id:
            details.append({"status": "error", "message": "order_id required"})
            failed += 1
            continue
        
        lab_order = get_lab_order_queryset(request.user, hospital).filter(id=order_id).first()
        if not lab_order:
            details.append({
                "order_id": order_id,
                "status": "error",
                "message": "Order not found"
            })
            failed += 1
            continue
        
        try:
            if lab_order.status != "in_progress":
                details.append(
                    {
                        "order_id": order_id,
                        "status": "error",
                        "message": f"Order must be in_progress before result submit. Current status: {lab_order.status}",
                    }
                )
                failed += 1
                continue

            attachment_url = item.get("attachment_url")
            if attachment_url:
                ok, err = _validate_attachment_url(
                    attachment_url,
                    content_type=item.get("attachment_content_type"),
                    size_bytes=item.get("attachment_size_bytes"),
                )
                if not ok:
                    details.append({
                        "order_id": order_id,
                        "status": "error",
                        "message": err
                    })
                    failed += 1
                    continue
            
            lab_result, _ = LabResult.objects.get_or_create(
                lab_order=lab_order,
                defaults={
                    "record": lab_order.record,
                    "test_name": lab_order.test_name,
                    "status": "pending",
                    "lab_tech": request.user,
                },
            )
            lab_result.result_value = item.get("result_value")
            lab_result.reference_range = item.get("reference_range")
            lab_result.status = "resulted"
            lab_result.lab_tech = request.user
            lab_result.attachment_url = attachment_url or None
            lab_result.save()

            lab_order.assigned_to = request.user
            lab_order.status = "resulted"
            lab_order.resulted_at = timezone.now()
            lab_order.save(update_fields=["assigned_to", "status", "resulted_at"])
            
            details.append({
                "order_id": order_id,
                "status": "success",
                "result_id": str(lab_result.id)
            })
            submitted += 1
        except Exception as e:
            details.append({
                "order_id": order_id,
                "status": "error",
                "message": str(e)
            })
            failed += 1
    
    audit_log(
        request.user,
        "LAB_BULK_SUBMIT",
        "lab_result",
        f"{submitted} results",
        hospital,
        request,
    )
    
    return Response({
        "submitted": submitted,
        "failed": failed,
        "details": details,
    }, status=status.HTTP_200_OK if submitted > 0 else status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lab_analytics_trends(request):
    if request.user.role != "lab_technician":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    today = now.date()
    hospital = get_effective_hospital(request)
    orders = get_lab_order_queryset(request.user, hospital).select_related("record")

    resulted_today = orders.filter(resulted_at__date=today)

    def avg_minutes_for(urgency):
        rows = list(resulted_today.filter(urgency=urgency).values_list("record__created_at", "resulted_at"))
        if not rows:
            return None
        mins = [int((r_at - o_at).total_seconds() / 60) for o_at, r_at in rows if o_at and r_at]
        if not mins:
            return None
        return int(sum(mins) / len(mins))

    avg_tat = {
        "stat_min": avg_minutes_for("stat"),
        "urgent_min": avg_minutes_for("urgent"),
        "routine_min": avg_minutes_for("routine"),
    }

    breached_rows = []
    breach_count = 0
    for o in orders.filter(status__in=["resulted", "verified"]).exclude(resulted_at__isnull=True):
        target = TAT_TARGETS.get(o.urgency, 1440)
        elapsed = int((o.resulted_at - o.record.created_at).total_seconds() / 60) if o.record and o.resulted_at else 0
        overdue = elapsed - target
        if overdue > 0 and o.resulted_at.date() == today:
            breach_count += 1
            breached_rows.append({"test_name": o.test_name, "overdue_minutes": overdue})

    pending = orders.filter(status__in=PENDING_STATUSES)
    bins = {"0-1h": 0, "1-4h": 0, "4-24h": 0, "24h+": 0}
    for o in pending:
        age_min = int((now - o.record.created_at).total_seconds() / 60) if o.record else 0
        if age_min < 60:
            bins["0-1h"] += 1
        elif age_min < 240:
            bins["1-4h"] += 1
        elif age_min < 1440:
            bins["4-24h"] += 1
        else:
            bins["24h+"] += 1

    throughput_today = orders.filter(resulted_at__date=today).count()
    yesterday = today - timezone.timedelta(days=1)
    throughput_yesterday = orders.filter(resulted_at__date=yesterday).count()
    seven_day_total = orders.filter(resulted_at__date__gte=today - timezone.timedelta(days=6), resulted_at__date__lte=today).count()
    seven_day_avg = round(seven_day_total / 7, 2)

    return Response(
        {
            "avg_tat_by_urgency": avg_tat,
            "breach_count": breach_count,
            "breached_orders": breached_rows[:20],
            "pending_by_age": bins,
            "throughput": {
                "today": throughput_today,
                "yesterday": throughput_yesterday,
                "seven_day_avg": seven_day_avg,
            },
        }
    )
