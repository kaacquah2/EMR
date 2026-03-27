"""Bed-level management: list beds by ward, create, update status."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Ward, Bed
from api.utils import get_request_hospital


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bed_list_by_ward(request, ward_id):
    """List beds for a ward. Query params: status (optional)."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    try:
        if hospital:
            ward = Ward.objects.get(id=ward_id, hospital=hospital)
        else:
            ward = Ward.objects.get(id=ward_id)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.user.role == "nurse" and request.user.ward_id != ward.id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = Bed.objects.filter(ward=ward, is_active=True).order_by("bed_code")
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    data = [
        {
            "id": str(b.id),
            "bed_code": b.bed_code,
            "status": b.status,
            "ward_id": str(ward.id),
            "ward_name": ward.ward_name,
        }
        for b in qs
    ]
    return Response({"data": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bed_create(request):
    """Create a bed in a ward. Body: ward_id, bed_code, status (optional)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ward_id = request.data.get("ward_id")
    bed_code = (request.data.get("bed_code") or "").strip()
    if not ward_id or not bed_code:
        return Response(
            {"message": "ward_id and bed_code required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        ward = Ward.objects.get(id=ward_id, hospital=hospital)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if Bed.objects.filter(ward=ward, bed_code=bed_code).exists():
        return Response(
            {"message": "Bed with this code already exists in ward"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    status_val = request.data.get("status") or "available"
    if status_val not in ("available", "occupied", "reserved", "maintenance"):
        status_val = "available"
    bed = Bed.objects.create(ward=ward, bed_code=bed_code, status=status_val)
    return Response(
        {
            "id": str(bed.id),
            "bed_code": bed.bed_code,
            "status": bed.status,
            "ward_id": str(ward.id),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def bed_update(request, bed_id):
    """Update bed status. Body: status (available|occupied|reserved|maintenance)."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    qs = Bed.objects.filter(id=bed_id).select_related("ward")
    if hospital:
        qs = qs.filter(ward__hospital=hospital)
    bed = qs.first()
    if not bed:
        return Response(
            {"message": "Bed not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.user.role == "nurse" and request.user.ward_id != bed.ward_id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    new_status = request.data.get("status")
    if new_status in ("available", "occupied", "reserved", "maintenance"):
        bed.status = new_status
        bed.save()
    return Response({
        "id": str(bed.id),
        "bed_code": bed.bed_code,
        "status": bed.status,
    })
