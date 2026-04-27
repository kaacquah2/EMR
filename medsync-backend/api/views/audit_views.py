from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.services.audit_service import compute_audit_chain_status


def _require_super_admin(request):
    if request.user.role != "super_admin":
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    return None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def validate_chain(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    try:
        out = compute_audit_chain_status(max_users=500, max_logs_per_user=2000)
        return Response(out)
    except Exception as e:
        return Response(
            {"status": "unknown", "last_checked_at": None, "message": str(e), "checked_entries": 0},
            status=status.HTTP_200_OK,
        )
