from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from patients.models import ClinicalAlert
from api.utils import get_effective_hospital
from api.pagination import paginate_queryset
from api.signals_alerts import broadcast_alert_resolved
from api.permissions import ALERT_RESOLVE_ROLES


def _alert_queryset(user, effective_hospital=None):
    from api.utils import _scope_hospital
    hospital = _scope_hospital(user, effective_hospital)
    qs = ClinicalAlert.objects.select_related("patient", "hospital", "created_by")
    if user.role == "super_admin" and not user.hospital_id and not hospital:
        return qs
    if hospital:
        return qs.filter(hospital=hospital)
    return qs.none()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alert_list(request):
    if request.user.role not in ("super_admin", "hospital_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = _alert_queryset(request.user, get_effective_hospital(request))
    resolved_raw = request.GET.get("resolved")
    if resolved_raw is not None and str(resolved_raw).lower() in ("false", "0", "no"):
        qs = qs.filter(status="active")
    elif request.GET.get("unresolved") in ("1", "true", "yes"):
        qs = qs.filter(status="active")
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    severity = request.GET.get("severity")
    if severity:
        qs = qs.filter(severity=severity)
    qs = qs.order_by("-created_at")
    total_count = qs.count()
    page, next_cursor, has_more = paginate_queryset(qs, request, page_size=50)
    data = [
        {
            "id": str(a.id),
            "patient_id": str(a.patient_id),
            "patient_name": a.patient.full_name,
            "ghana_health_id": a.patient.ghana_health_id,
            "severity": a.severity,
            "message": a.message,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        }
        for a in page
    ]
    return Response({
        "data": data,
        "total_count": total_count,
        "next_cursor": next_cursor,
        "has_more": has_more,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def alert_resolve(request, pk):
    if request.user.role not in ALERT_RESOLVE_ROLES:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = _alert_queryset(request.user, get_effective_hospital(request))
    alert = qs.filter(id=pk).first()
    if not alert:
        return Response(
            {"message": "Alert not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    alert.status = "resolved"
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save(update_fields=["status", "resolved_at", "resolved_by"])
    broadcast_alert_resolved(alert)
    return Response({
        "id": str(alert.id),
        "status": alert.status,
        "resolved_at": alert.resolved_at.isoformat(),
    })
