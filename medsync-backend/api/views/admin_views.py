import csv
import io
import secrets
import pyotp
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from core.models import User, Hospital, Ward, Department, LabUnit, AuditLog, Bed
from patients.models import PatientAdmission
from api.serializers import UserSerializer, WardSerializer
from api.utils import sanitize_audit_resource_id, get_request_hospital, audit_log, get_hospital_for_super_admin_override
from api.pagination import paginate_queryset

try:
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
except ImportError:
    OutstandingToken = None
    BlacklistedToken = None


_USER_ORDERING = {
    "last_login": "last_login",
    "-last_login": "-last_login",
    "created_at": "created_at",
    "-created_at": "-created_at",
}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_list(request):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "hospital_admin" and not hospital:
        return Response({"data": [], "total_count": 0, "next_cursor": None, "has_more": False})
    qs = User.objects.all()
    if hospital:
        qs = qs.filter(hospital=hospital)
    role = request.GET.get("role")
    if role:
        qs = qs.filter(role=role)
    status_filter = request.GET.get("status") or request.GET.get("account_status")
    if status_filter:
        qs = qs.filter(account_status=status_filter)
    ordering = (request.GET.get("ordering") or "").strip()
    order_by = _USER_ORDERING.get(ordering, "-created_at")
    qs = qs.select_related("hospital", "ward", "department_link", "lab_unit").order_by(order_by)
    total_count = qs.count()
    if request.GET.get("count_only") in ("1", "true", "yes"):
        return Response({"count": total_count})
    page, next_cursor, has_more = paginate_queryset(qs, request, page_size=20, max_page_size=100)
    return Response({
        "data": UserSerializer(page, many=True).data,
        "total_count": total_count,
        "next_cursor": next_cursor,
        "has_more": has_more,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_invite(request):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "hospital_admin" and not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.user.role == "super_admin" and not hospital:
        hospital_id = request.data.get("hospital_id")
        if not hospital_id:
            return Response(
                {"message": "hospital_id required for super_admin"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            return Response(
                {"message": "Hospital not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
    data = request.data
    email = (data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"message": "Email required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {"message": "User with this email already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    role = data.get("role")
    if request.user.role == "super_admin":
        if role != "hospital_admin":
            return Response(
                {"message": "Super Admin can only create Hospital Administrators. Staff (doctors, nurses, etc.) are invited by each hospital's admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        if role not in ("doctor", "nurse", "receptionist", "lab_technician", "pharmacist", "radiology_technician", "billing_staff", "ward_clerk"):
            return Response(
                {"message": "Invalid role"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    ward_id = data.get("ward_id") if role == "nurse" else None
    ward = None
    if ward_id:
        try:
            ward = Ward.objects.get(id=ward_id, hospital=hospital)
        except Ward.DoesNotExist:
            return Response(
                {"message": "Ward not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    department_link = None
    dep_id = data.get("department_id")
    if dep_id:
        try:
            department_link = Department.objects.get(id=dep_id, hospital=hospital)
        except Department.DoesNotExist:
            pass
    lab_unit = None
    if role == "lab_technician":
        unit_id = data.get("lab_unit_id")
        if unit_id:
            try:
                lab_unit = LabUnit.objects.get(id=unit_id, hospital=hospital)
            except LabUnit.DoesNotExist:
                pass
    token = secrets.token_urlsafe(48)
    totp_secret = pyotp.random_base32()
    dept_name = department_link.name if department_link else (data.get("department") or "").strip()
    user = User.objects.create(
        hospital=hospital,
        email=email,
        role=role,
        full_name=data.get("full_name", ""),
        department=dept_name,
        department_link=department_link,
        ward=ward,
        lab_unit=lab_unit,
        account_status="pending",
        invitation_token=token,
        invitation_expires_at=timezone.now() + timedelta(hours=24),
        invited_by=request.user,
        totp_secret=totp_secret,
    )
    if role == "doctor":
        user.gmdc_licence_number = data.get("gmdc_licence_number") or None
        user.save(update_fields=["gmdc_licence_number"])
    audit_log(request.user, "INVITE_SENT", "user", str(user.id), hospital, request)
    return Response(
        {"message": "Invitation sent", "user_id": str(user.id)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def user_bulk_import(request):
    """Accept a CSV file with columns: email, full_name, role[, department, ward_id, gmdc_licence_number]. Creates pending users with invitation tokens. Super Admin cannot use bulk import; they create hospital admins one at a time."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if request.user.role == "super_admin":
        return Response(
            {"message": "Bulk import is for hospital admins only. Use Invite to create hospital administrators."},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "hospital_admin" and not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.user.role == "super_admin":
        hospital_id = request.data.get("hospital_id") or request.data.get("hospital")
        if not hospital_id:
            return Response(
                {"message": "hospital_id required for super_admin"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            return Response(
                {"message": "Hospital not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
    file = request.FILES.get("file") or request.data.get("file")
    if not file:
        return Response(
            {"message": "CSV file required (form field: file)"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB
    MAX_CSV_ROWS = 500
    file_obj = file if hasattr(file, "read") else getattr(file, "file", file)
    size = getattr(file_obj, "size", None)
    if size is not None and size > MAX_CSV_BYTES:
        return Response(
            {"message": f"File too large. Maximum size is {MAX_CSV_BYTES // (1024 * 1024)} MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        content = file.read(MAX_CSV_BYTES + 1).decode("utf-8-sig")
    except Exception:
        return Response(
            {"message": "Invalid file encoding"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(content) > MAX_CSV_BYTES:
        return Response(
            {"message": f"File too large. Maximum size is {MAX_CSV_BYTES // (1024 * 1024)} MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    reader = csv.DictReader(io.StringIO(content))
    required = {"email", "full_name", "role"}
    created = 0
    errors = []
    row_limit = MAX_CSV_ROWS + 1  # header is row 1
    for i, row in enumerate(reader, start=2):
        if i > row_limit:
            errors.append({"row": i, "error": f"Row limit exceeded ({MAX_CSV_ROWS} rows). Processed first {MAX_CSV_ROWS} rows only."})
            break
        row = {k.strip().lower().replace(" ", "_"): v for k, v in row.items() if k}
        if not required.issubset(row):
            errors.append({"row": i, "error": "Missing email, full_name, or role"})
            continue
        email = (row.get("email") or "").strip().lower()
        full_name = (row.get("full_name") or "").strip()
        role = (row.get("role") or "").strip().lower()
        if not email:
            errors.append({"row": i, "error": "Empty email"})
            continue
        if role not in ("doctor", "nurse", "receptionist", "lab_technician", "pharmacist", "radiology_technician", "billing_staff", "ward_clerk"):
            errors.append({"row": i, "error": f"Invalid role: {role}"})
            continue
        if User.objects.filter(email__iexact=email).exists():
            errors.append({"row": i, "email": email, "error": "User already exists"})
            continue
        ward_id = (row.get("ward_id") or "").strip() or None
        ward = None
        if ward_id and role == "nurse":
            try:
                ward = Ward.objects.get(id=ward_id, hospital=hospital)
            except (Ward.DoesNotExist, ValueError):
                errors.append({"row": i, "email": email, "error": "Invalid ward_id"})
                continue
        try:
            token = secrets.token_urlsafe(48)
            totp_secret = pyotp.random_base32()
            user = User.objects.create(
                hospital=hospital,
                email=email,
                role=role,
                full_name=full_name or email,
                department=(row.get("department") or "").strip(),
                ward=ward,
                account_status="pending",
                invitation_token=token,
                invitation_expires_at=timezone.now() + timedelta(hours=24),
                invited_by=request.user,
                totp_secret=totp_secret,
            )
            if role == "doctor":
                user.gmdc_licence_number = (row.get("gmdc_licence_number") or "").strip() or None
                user.save(update_fields=["gmdc_licence_number"])
            audit_log(request.user, "INVITE_SENT", "user", str(user.id), hospital, request)
            created += 1
        except Exception as e:
            errors.append({"row": i, "email": email, "error": str(e)})
    return Response({
        "message": f"Created {created} user(s)",
        "created": created,
        "errors": errors,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = AuditLog.objects.all().select_related("user", "hospital")
    if request.user.role == "hospital_admin":
        qs = qs.filter(hospital=get_request_hospital(request))

    action = request.GET.get("action", "").strip()
    if action:
        qs = qs.filter(action=action)

    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            qs = qs.filter(timestamp__date__gte=dt.date())
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            qs = qs.filter(timestamp__date__lte=dt.date())
        except ValueError:
            pass

    qs = qs.order_by("-timestamp")
    page, next_cursor, has_more = paginate_queryset(qs, request, page_size=50, max_page_size=200)
    return Response({
        "data": [
            {
                "log_id": str(log.id),
                "user": log.user.full_name,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "timestamp": log.timestamp.isoformat(),
                "ip_address": str(log.ip_address),
                "hospital": log.hospital.name if log.hospital else None,
            }
            for log in page
        ],
        "next_cursor": next_cursor,
        "has_more": has_more,
    })


def _get_admin_target_user(request, pk):
    """Return target user if request.user (hospital_admin or super_admin) is allowed to manage them. Else (None, Response)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return None, Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    qs = User.objects.all()
    if request.user.role == "hospital_admin":
        qs = qs.filter(hospital=get_request_hospital(request))
    try:
        return qs.get(id=pk), None
    except (User.DoesNotExist, ValueError):
        return None, Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_send_password_reset(request, pk):
    """Admin-initiated password reset: set reset token so user can use reset-password flow. Hospital admin: own hospital only; super_admin: any."""
    target, err = _get_admin_target_user(request, pk)
    if err:
        return err
    if target.account_status != "active":
        return Response(
            {"message": "Only active accounts can receive a password reset. Use Resend invite for pending users."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    target.invitation_token = secrets.token_urlsafe(48)
    target.invitation_expires_at = timezone.now() + timedelta(hours=1)
    target.save()
    audit_log(request.user, "ADMIN_PASSWORD_RESET_SENT", "user", str(target.id), target.hospital, request)
    return Response({
        "message": "Password reset token generated. Use the token to build the reset link for the user.",
        "token": target.invitation_token,
        "expires_in_hours": 1,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_reset_mfa(request, pk):
    """Clear user MFA so they must set it up again on next login. Hospital admin: own hospital only; super_admin: any."""
    target, err = _get_admin_target_user(request, pk)
    if err:
        return err
    if target.account_status != "active":
        return Response(
            {"message": "Only active accounts have MFA. Activate the account first."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    target.is_mfa_enabled = False
    target.totp_secret = pyotp.random_base32()
    target.mfa_backup_codes = None
    target.save()
    audit_log(request.user, "ADMIN_MFA_RESET", "user", str(target.id), target.hospital, request)
    return Response({"message": "MFA reset. User must set up MFA again on next login."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def user_resend_invite(request, pk):
    """Resend invitation (new token, 24h expiry) for pending users. Hospital admin: own hospital only; super_admin: any."""
    target, err = _get_admin_target_user(request, pk)
    if err:
        return err
    if target.account_status != "pending":
        return Response(
            {"message": "Only pending (not yet activated) users can receive a new invite. Use Send password reset for active users."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    target.invitation_token = secrets.token_urlsafe(48)
    target.invitation_expires_at = timezone.now() + timedelta(hours=24)
    target.save()
    audit_log(request.user, "INVITE_RESENT", "user", str(target.id), target.hospital, request)
    return Response({
        "message": "Invitation resent. Use the token to build the activation link for the user.",
        "token": target.invitation_token,
        "expires_in_hours": 24,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def user_update(request, pk):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = User.objects.all()
    if request.user.role == "hospital_admin":
        qs = qs.filter(hospital=get_request_hospital(request))
    try:
        target = qs.get(id=pk)
    except (User.DoesNotExist, ValueError):
        return Response(
            {"message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    data = request.data
    old_role = target.role
    old_status = target.account_status
    if "account_status" in data and data["account_status"] is not None:
        if data["account_status"] in ("active", "inactive", "pending", "suspended", "locked"):
            target.account_status = data["account_status"]
    requested_role = data.get("role")
    if request.user.role == "super_admin":
        if "hospital_id" in data:
            if data["hospital_id"] is None:
                target.hospital = None
            else:
                try:
                    target.hospital = Hospital.objects.get(id=data["hospital_id"])
                except Hospital.DoesNotExist:
                    pass
        if requested_role in ("super_admin", "hospital_admin", "doctor", "nurse", "receptionist", "lab_technician", "pharmacist", "radiology_technician", "billing_staff", "ward_clerk"):
            target.role = requested_role
    elif request.user.role == "hospital_admin" and requested_role in ("doctor", "nurse", "receptionist", "lab_technician", "pharmacist", "radiology_technician", "billing_staff", "ward_clerk"):
        # Hospital admins can reassign roles for clinical/admin staff in their own facility.
        if target.role in ("super_admin", "hospital_admin"):
            return Response(
                {"message": "Hospital admin cannot change admin-level roles"},
                status=status.HTTP_403_FORBIDDEN,
            )
        target.role = requested_role
    if "full_name" in data and data["full_name"] is not None:
        target.full_name = (data["full_name"] or "").strip()
    if "department" in data:
        target.department = (data["department"] or "").strip()
    if "department_id" in data and target.hospital_id:
        if data["department_id"]:
            try:
                target.department_link = Department.objects.get(id=data["department_id"], hospital=target.hospital)
                target.department = target.department_link.name
            except Department.DoesNotExist:
                target.department_link = None
        else:
            target.department_link = None
    if "lab_unit_id" in data and target.role == "lab_technician" and target.hospital_id:
        if data["lab_unit_id"]:
            try:
                target.lab_unit = LabUnit.objects.get(id=data["lab_unit_id"], hospital=target.hospital)
            except LabUnit.DoesNotExist:
                target.lab_unit = None
        else:
            target.lab_unit = None
    if "ward_id" in data and target.role == "nurse":
        if data["ward_id"]:
            try:
                target.ward = Ward.objects.get(id=data["ward_id"], hospital=target.hospital)
            except Ward.DoesNotExist:
                pass
        else:
            target.ward = None
    if "gmdc_licence_number" in data and target.role == "doctor":
        target.gmdc_licence_number = (data["gmdc_licence_number"] or "").strip() or None
    if request.user.role == "super_admin" and "licence_verified" in data and target.role == "doctor":
        target.licence_verified = bool(data["licence_verified"])
    if target.role != "nurse":
        target.ward = None
    if target.role != "lab_technician":
        target.lab_unit = None
    if target.role != "doctor":
        target.gmdc_licence_number = None
        if request.user.role == "super_admin":
            target.licence_verified = False
    if "last_role_reviewed_at" in data:
        raw = data["last_role_reviewed_at"]
        if raw in (None, ""):
            target.last_role_reviewed_at = None
        else:
            dt = parse_datetime(str(raw)) if not isinstance(raw, datetime) else raw
            if dt is not None:
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                target.last_role_reviewed_at = dt
    target.save()
    if target.role != old_role:
        audit_log(
            request.user,
            "ROLE_CHANGE",
            "user",
            str(target.id),
            target.hospital,
            request,
            extra_data={"from_role": old_role, "to_role": target.role, "reason": data.get("reason")},
        )
    if (target.role != old_role or target.account_status != old_status) and OutstandingToken is not None and BlacklistedToken is not None:
        for ot in OutstandingToken.objects.filter(user_id=target.id):
            BlacklistedToken.objects.get_or_create(token=ot)
    return Response(UserSerializer(target).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def user_role_review(request, pk):
    """Mark role review (same as PATCH /admin/users/<pk> with last_role_reviewed_at)."""
    return user_update(request, pk)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ward_list(request):
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    include_inactive = request.GET.get("include_inactive") in ("1", "true", "yes")
    wards = Ward.objects.filter(hospital=hospital)
    if not include_inactive:
        wards = wards.filter(is_active=True)
    wards = wards.order_by("ward_name")
    return Response({"data": WardSerializer(wards, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ward_occupancy(request):
    """Per-ward bed counts for hospital admin dashboard."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    rows = []
    for w in Ward.objects.filter(hospital=hospital).order_by("ward_name"):
        total_beds = Bed.objects.filter(ward=w, is_active=True).count()
        occupied = PatientAdmission.objects.filter(ward=w, discharged_at__isnull=True).count()
        rows.append({
            "id": str(w.id),
            "name": w.ward_name,
            "ward_type": w.ward_type,
            "total_beds": total_beds,
            "occupied_beds": occupied,
            "is_active": w.is_active,
        })
    return Response({"data": rows})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ward_create(request):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin":
        hid = request.data.get("hospital_id")
        if not hid:
            return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hospital = Hospital.objects.get(id=hid)
        except Hospital.DoesNotExist:
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "No hospital assigned"}, status=status.HTTP_400_BAD_REQUEST)
    name = (request.data.get("name") or request.data.get("ward_name") or "").strip()
    if not name:
        return Response({"message": "name required"}, status=status.HTTP_400_BAD_REQUEST)
    ward_type = (request.data.get("type") or request.data.get("ward_type") or "general").strip()
    allowed = {c[0] for c in Ward.WARD_TYPES}
    if ward_type not in allowed:
        ward_type = "general"
    ward, created = Ward.objects.get_or_create(
        hospital=hospital,
        ward_name=name,
        defaults={"ward_type": ward_type, "is_active": True},
    )
    if not created:
        return Response({"message": "Ward already exists", "ward_id": str(ward.id)}, status=status.HTTP_200_OK)
    audit_log(request.user, "CREATE", "ward", str(ward.id), hospital, request)
    return Response({"ward_id": str(ward.id), "name": ward.ward_name, "ward_type": ward.ward_type}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def ward_update(request, ward_id):
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.data.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.data.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "No hospital assigned"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        ward = Ward.objects.get(id=ward_id, hospital=hospital)
    except Ward.DoesNotExist:
        return Response({"message": "Ward not found"}, status=status.HTTP_404_NOT_FOUND)
    if "is_active" in request.data:
        ward.is_active = bool(request.data["is_active"])
    if "ward_name" in request.data or "name" in request.data:
        nm = (request.data.get("ward_name") or request.data.get("name") or "").strip()
        if nm:
            ward.ward_name = nm
    if "ward_type" in request.data or "type" in request.data:
        wt = (request.data.get("ward_type") or request.data.get("type") or "").strip()
        if wt in {c[0] for c in Ward.WARD_TYPES}:
            ward.ward_type = wt
    ward.save()
    return Response(WardSerializer(ward).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ward_create_beds(request, ward_id):
    """Bulk-create beds with generated codes (BED-1, BED-2, ...)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"message": "No hospital assigned"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        ward = Ward.objects.get(id=ward_id, hospital=hospital)
    except Ward.DoesNotExist:
        return Response({"message": "Ward not found"}, status=status.HTTP_404_NOT_FOUND)
    try:
        count = int(request.data.get("count", 0))
    except (TypeError, ValueError):
        count = 0
    if count < 1 or count > 200:
        return Response({"message": "count must be between 1 and 200"}, status=status.HTTP_400_BAD_REQUEST)
    base = Bed.objects.filter(ward=ward).count()
    created_ids = []
    for i in range(count):
        n = base + i + 1
        code = f"BED-{n}"
        while Bed.objects.filter(ward=ward, bed_code=code).exists():
            n += 1
            code = f"BED-{n}"
        b = Bed.objects.create(ward=ward, bed_code=code, status="available", is_active=True)
        created_ids.append(str(b.id))
    audit_log(request.user, "CREATE", "bed_bulk", str(ward.id), hospital, request)
    return Response({"created": len(created_ids), "bed_ids": created_ids}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rbac_review_list(request):
    """Staff with last role review date and days overdue (90-day policy)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    rows = []
    today = timezone.now().date()
    for u in (
        User.objects.filter(hospital=hospital)
        .exclude(role__in=("super_admin", "hospital_admin"))
        .select_related("hospital")
        .order_by("full_name")
    ):
        anchor = u.last_role_reviewed_at or u.created_at
        if anchor is None:
            days_since = 0
        else:
            days_since = (today - anchor.date()).days
        days_overdue = max(0, days_since - 90)
        rows.append({
            "user_id": str(u.id),
            "full_name": u.full_name,
            "role": u.role,
            "last_role_reviewed_at": u.last_role_reviewed_at.isoformat() if u.last_role_reviewed_at else None,
            "days_overdue": days_overdue,
        })
    rows.sort(key=lambda r: (-r["days_overdue"], r["full_name"]))
    return Response({"data": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def department_list(request):
    """List departments for the hospital (workflow routing, user assignment)."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse", "receptionist"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    depts = Department.objects.filter(hospital=hospital, is_active=True).order_by("name")
    return Response({
        "data": [{"department_id": str(d.id), "name": d.name} for d in depts],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def department_create(request):
    """Create a department for the hospital (workflow setup)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin":
        hid = request.data.get("hospital_id")
        if not hid:
            return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hospital = Hospital.objects.get(id=hid)
        except Hospital.DoesNotExist:
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "No hospital"}, status=status.HTTP_400_BAD_REQUEST)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"message": "name required"}, status=status.HTTP_400_BAD_REQUEST)
    dept, created = Department.objects.get_or_create(hospital=hospital, name=name, defaults={"is_active": True})
    return Response(
        {"department_id": str(dept.id), "name": dept.name},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lab_unit_list(request):
    """List lab units for the hospital (lab tech assignment, lab order routing)."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "lab_technician"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    units = LabUnit.objects.filter(hospital=hospital, is_active=True).order_by("name")
    return Response({
        "data": [{"lab_unit_id": str(u.id), "name": u.name} for u in units],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lab_unit_create(request):
    """Create a lab unit for the hospital (workflow setup)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin":
        hid = request.data.get("hospital_id")
        if not hid:
            return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hospital = Hospital.objects.get(id=hid)
        except Hospital.DoesNotExist:
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "No hospital"}, status=status.HTTP_400_BAD_REQUEST)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"message": "name required"}, status=status.HTTP_400_BAD_REQUEST)
    unit, created = LabUnit.objects.get_or_create(hospital=hospital, name=name, defaults={"is_active": True})
    return Response(
        {"lab_unit_id": str(unit.id), "name": unit.name},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lab_test_type_list(request):
    """List lab test types (test name -> lab unit) for ordering. Used by doctor when creating lab order."""
    from records.models import LabTestType
    if request.user.role not in ("hospital_admin", "super_admin", "doctor"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    types = (
        LabTestType.objects.filter(lab_unit__hospital=hospital, is_active=True)
        .select_related("lab_unit")
        .order_by("test_name")
    )
    return Response({
        "data": [
            {"test_name": t.test_name, "lab_unit_id": str(t.lab_unit_id), "lab_unit_name": t.lab_unit.name, "specimen": t.specimen or ""}
            for t in types
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lab_test_type_create(request):
    """Create a lab test type (test name -> lab unit) for routing. Hospital admin / super_admin."""
    from records.models import LabTestType
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin":
        hid = request.data.get("hospital_id")
        if not hid:
            return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hospital = Hospital.objects.get(id=hid)
        except Hospital.DoesNotExist:
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "No hospital"}, status=status.HTTP_400_BAD_REQUEST)
    lab_unit_id = request.data.get("lab_unit_id")
    if not lab_unit_id:
        return Response({"message": "lab_unit_id required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        lab_unit = LabUnit.objects.get(id=lab_unit_id, hospital=hospital)
    except LabUnit.DoesNotExist:
        return Response({"message": "Lab unit not found"}, status=status.HTTP_404_NOT_FOUND)
    test_name = (request.data.get("test_name") or "").strip()
    if not test_name:
        return Response({"message": "test_name required"}, status=status.HTTP_400_BAD_REQUEST)
    specimen = (request.data.get("specimen") or "").strip()
    obj, created = LabTestType.objects.get_or_create(
        lab_unit=lab_unit, test_name=test_name, defaults={"specimen": specimen or "", "is_active": True}
    )
    return Response(
        {"test_name": obj.test_name, "lab_unit_id": str(obj.lab_unit_id), "specimen": obj.specimen or ""},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def doctor_list(request):
    """List doctors for the hospital (encounter assignment dropdown). Optionally filter by department_id."""
    if request.user.role not in ("hospital_admin", "super_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and request.GET.get("hospital_id"):
        try:
            hospital = Hospital.objects.get(id=request.GET.get("hospital_id"))
        except (Hospital.DoesNotExist, ValueError):
            return Response({"data": []})
    if not hospital:
        return Response({"data": []})
    qs = User.objects.filter(hospital=hospital, role="doctor", account_status="active").select_related("department_link")
    dep_id = request.GET.get("department_id")
    if dep_id:
        qs = qs.filter(department_link_id=dep_id)
    qs = qs.order_by("full_name")
    return Response({
        "data": [
            {"user_id": str(u.id), "full_name": u.full_name, "department_id": str(u.department_link_id) if u.department_link_id else None, "department_name": u.department_link.name if u.department_link else None}
            for u in qs
        ],
    })


# ---- Possible duplicates queue (admin / HIM) ----

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def duplicate_list(request):
    """List possible duplicate pairs for admin review. Hospital-scoped; super_admin sees all."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    from patients.models import PotentialDuplicate, Patient
    hospital = get_request_hospital(request)
    if request.user.role == "hospital_admin" and not hospital:
        return Response({"data": []})
    qs = PotentialDuplicate.objects.all().select_related(
        "patient_a", "patient_b", "hospital", "reviewed_by", "created_by"
    )
    if request.user.role == "hospital_admin":
        qs = qs.filter(hospital=hospital)
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs.order_by("-created_at")[:100]
    data = [
        {
            "id": str(d.id),
            "patient_a_id": str(d.patient_a_id),
            "patient_a_name": d.patient_a.full_name,
            "patient_a_ghana_health_id": d.patient_a.ghana_health_id,
            "patient_b_id": str(d.patient_b_id),
            "patient_b_name": d.patient_b.full_name,
            "patient_b_ghana_health_id": d.patient_b.ghana_health_id,
            "hospital_id": str(d.hospital_id),
            "status": d.status,
            "reviewed_by": d.reviewed_by.full_name if d.reviewed_by else None,
            "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
            "merged_into_patient_id": str(d.merged_into_patient_id) if d.merged_into_patient_id else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in qs
    ]
    return Response({"data": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def duplicate_create(request):
    """Submit a possible duplicate pair for review. Hospital admin / super_admin."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    from patients.models import PotentialDuplicate, Patient
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin":
        hid = request.data.get("hospital_id")
        if hid:
            try:
                hospital = Hospital.objects.get(id=hid)
            except Hospital.DoesNotExist:
                return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
    patient_a_id = request.data.get("patient_a_id")
    patient_b_id = request.data.get("patient_b_id")
    if not patient_a_id or not patient_b_id:
        return Response(
            {"message": "patient_a_id and patient_b_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if patient_a_id == patient_b_id:
        return Response(
            {"message": "patient_a_id and patient_b_id must be different"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    pa = Patient.objects.filter(id=patient_a_id, registered_at=hospital).first()
    pb = Patient.objects.filter(id=patient_b_id, registered_at=hospital).first()
    if not pa or not pb:
        return Response(
            {"message": "Both patients must exist and belong to the hospital"},
            status=status.HTTP_404_NOT_FOUND,
        )
    existing = PotentialDuplicate.objects.filter(
        hospital=hospital,
        patient_a__in=[pa, pb],
        patient_b__in=[pa, pb],
        status="pending",
    ).exists()
    if existing:
        return Response(
            {"message": "A pending duplicate record for this pair already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    dup = PotentialDuplicate.objects.create(
        hospital=hospital,
        patient_a=pa,
        patient_b=pb,
        status="pending",
        created_by=request.user,
    )
    return Response(
        {
            "id": str(dup.id),
            "patient_a_id": str(dup.patient_a_id),
            "patient_b_id": str(dup.patient_b_id),
            "status": dup.status,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def duplicate_detail(request, duplicate_id):
    """Get or review a possible duplicate. PATCH: set status (not_duplicate, approved_duplicate) or merge (merged, merged_into_patient_id)."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    from patients.models import PotentialDuplicate
    dup = PotentialDuplicate.objects.filter(id=duplicate_id).select_related(
        "patient_a", "patient_b", "hospital", "reviewed_by"
    ).first()
    if not dup:
        return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    req_h = get_request_hospital(request)
    if req_h and dup.hospital_id != req_h.id:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        return Response({
            "id": str(dup.id),
            "patient_a_id": str(dup.patient_a_id),
            "patient_a_name": dup.patient_a.full_name,
            "patient_a_ghana_health_id": dup.patient_a.ghana_health_id,
            "patient_b_id": str(dup.patient_b_id),
            "patient_b_name": dup.patient_b.full_name,
            "patient_b_ghana_health_id": dup.patient_b.ghana_health_id,
            "hospital_id": str(dup.hospital_id),
            "status": dup.status,
            "reviewed_by": dup.reviewed_by.full_name if dup.reviewed_by else None,
            "reviewed_at": dup.reviewed_at.isoformat() if dup.reviewed_at else None,
            "merged_into_patient_id": str(dup.merged_into_patient_id) if dup.merged_into_patient_id else None,
            "created_at": dup.created_at.isoformat(),
        })
    if request.method == "PATCH":
        data = request.data
        new_status = (data.get("status") or "").strip()
        if new_status in ("not_duplicate", "approved_duplicate"):
            dup.status = new_status
            dup.reviewed_by = request.user
            dup.reviewed_at = timezone.now()
            dup.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            return Response({"id": str(dup.id), "status": dup.status})
        if new_status == "merged":
            survivor_id = data.get("merged_into_patient_id")
            if not survivor_id or str(survivor_id) not in (str(dup.patient_a_id), str(dup.patient_b_id)):
                return Response(
                    {"message": "merged_into_patient_id must be patient_a_id or patient_b_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            dup.status = "merged"
            dup.merged_into_patient_id = survivor_id
            dup.reviewed_by = request.user
            dup.reviewed_at = timezone.now()
            dup.save(update_fields=["status", "merged_into_patient_id", "reviewed_by", "reviewed_at"])
            return Response({
                "id": str(dup.id),
                "status": dup.status,
                "merged_into_patient_id": str(dup.merged_into_patient_id),
            })
        return Response({"message": "Invalid status or missing merged_into_patient_id for merge"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


# PHASE 6: Hospital Admin Staff Training & Onboarding


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def staff_onboarding_dashboard(request):
    """Staff onboarding status dashboard for hospital admin."""
    if request.user.role not in ("hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"data": []})
    
    users = User.objects.filter(hospital=hospital).order_by("-created_at")
    
    data = []
    for user in users:
        # Onboarding status
        account_activated = user.account_status == "active"
        mfa_setup = user.is_mfa_enabled
        license_verified = user.licence_verified if user.role == "doctor" else None
        
        training_status = "not_started"
        if account_activated and mfa_setup:
            training_status = "in_progress"
        if account_activated and mfa_setup and (license_verified or user.role != "doctor"):
            training_status = "complete"
        
        data.append({
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "onboarding": {
                "invited_at": user.created_at.isoformat(),
                "account_activated": account_activated,
                "mfa_setup": mfa_setup,
                "license_verified": license_verified,
                "status": training_status,
            }
        })
    
    return Response({
        "total_staff": len(data),
        "by_status": {
            "not_started": sum(1 for d in data if d["onboarding"]["status"] == "not_started"),
            "in_progress": sum(1 for d in data if d["onboarding"]["status"] == "in_progress"),
            "complete": sum(1 for d in data if d["onboarding"]["status"] == "complete"),
        },
        "staff": data,
    })
