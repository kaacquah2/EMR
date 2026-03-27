import csv
import io
import hashlib
import hmac
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from core.models import Hospital, User, AuditLog, Ward, Department, LabUnit, SuperAdminHospitalAccess
from interop.models import BreakGlassLog, FacilityPatient, Consent, Referral
from api.utils import audit_log


def _require_super_admin(request):
    if request.user.role != "super_admin":
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _compute_audit_chain_status(max_users=200, max_logs_per_user=2000):
    """
    Validate AuditLog chain_hash and signature per user (tamper-evident).
    Bounds validation to avoid long request time in large deployments.
    """
    # NOTE: chain is per-user in core.models.AuditLog.save()
    user_ids = (
        AuditLog.objects.values_list("user_id", flat=True)
        .distinct()
        .order_by()[:max_users]
    )
    signing_key = None
    try:
        from django.conf import settings
        signing_key = getattr(settings, "AUDIT_LOG_SIGNING_KEY", "dev-key-change-in-production").encode()
    except Exception:
        signing_key = b"dev-key-change-in-production"

    checked = 0
    for uid in user_ids:
        prev_hash = "0"
        logs = (
            AuditLog.objects.filter(user_id=uid)
            .order_by("timestamp")
            .only("user_id", "action", "resource_type", "resource_id", "chain_hash", "signature", "timestamp")[:max_logs_per_user]
        )
        for log in logs:
            data = f"{prev_hash}{log.user_id}{log.action}{log.resource_type or ''}{log.resource_id or ''}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            expected_sig = hmac.new(signing_key, data.encode(), hashlib.sha256).hexdigest()
            checked += 1
            if log.chain_hash != expected_hash or (log.signature and log.signature != expected_sig):
                return {
                    "status": "invalid",
                    "last_checked_at": timezone.now().isoformat(),
                    "message": f"Mismatch at {str(log.id) if getattr(log, 'id', None) else ''} user={uid} ts={log.timestamp.isoformat()}",
                    "checked_entries": checked,
                }
            prev_hash = log.chain_hash
    return {
        "status": "valid",
        "last_checked_at": timezone.now().isoformat(),
        "message": None,
        "checked_entries": checked,
    }


def _hospitals_list_data():
    """
    Get hospitals with counts. Optimized to avoid N+1 queries.
    Uses aggregation and prefetch instead of per-hospital loops.
    """
    from django.db.models import Count, Q, Prefetch
    from patients.models import Patient
    
    # Single query with aggregation (kills N+1)
    hospitals = Hospital.objects.annotate(
        staff_count=Count('user', distinct=True),
        hospital_admin_count=Count(
            'user',
            filter=Q(user__role='hospital_admin', user__account_status__in=['pending', 'active']),
            distinct=True
        ),
        ward_count=Count('ward', distinct=True),
        department_count=Count('department', distinct=True),
        lab_unit_count=Count('labunit', distinct=True),
        doctor_count=Count('user', filter=Q(user__role='doctor'), distinct=True),
    ).all()
    
    # Prefetch patient counts (one query for all hospitals)
    facility_patients = FacilityPatient.objects.filter(deleted_at__isnull=True).values('facility_id').annotate(count=Count('global_patient_id', distinct=True))
    patient_counts = {fp['facility_id']: fp['count'] for fp in facility_patients}
    
    # Check if patients exist in any hospital (one query)
    hospital_ids_with_patients = set(Patient.objects.values_list('registered_at_id', flat=True).distinct())
    
    data = []
    for h in hospitals:
        # All checks now come from already-annotated counts
        checks = [
            h.ward_count > 0,
            h.department_count > 0,
            h.lab_unit_count > 0,
            h.doctor_count > 0,
            h.id in hospital_ids_with_patients,
        ]
        onboarding_pct = int(round((sum(1 for ok in checks if ok) / len(checks)) * 100))
        
        data.append(
            {
                "hospital_id": str(h.id),
                "id": str(h.id),
                "name": h.name,
                "region": h.region,
                "nhis_code": h.nhis_code,
                "is_active": h.is_active,
                "user_count": h.staff_count,
                "staff_count": h.staff_count,
                "patient_count": patient_counts.get(h.id, 0),
                "hospital_admin_count": h.hospital_admin_count,
                "onboarding_pct": onboarding_pct,
                "created_at": h.onboarded_at.isoformat() if h.onboarded_at else None,
            }
        )
    return data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hospitals_list(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    data = _hospitals_list_data()
    return Response({"data": data, "count": len(data)})


def _hospital_onboarding_list_data():
    hospitals = Hospital.objects.all().order_by("name")
    out = []
    for h in hospitals:
        checks = [
            ("Wards created", Ward.objects.filter(hospital=h).exists()),
            ("Departments created", Department.objects.filter(hospital=h).exists()),
            ("Lab units created", LabUnit.objects.filter(hospital=h).exists()),
            ("First doctor invited", User.objects.filter(hospital=h, role="doctor").exists()),
        ]
        try:
            from patients.models import Patient
            checks.append(("First patient registered", Patient.objects.filter(registered_at=h).exists()))
        except Exception:
            checks.append(("First patient registered", False))

        missing = [name for (name, ok) in checks if not ok]
        completion = int(round(((len(checks) - len(missing)) / len(checks)) * 100))
        out.append(
            {
                "hospital_id": str(h.id),
                "name": h.name,
                "completion_pct": completion,
                "missing_items": missing,
            }
        )
    return out


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hospital_onboarding_list(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    out = _hospital_onboarding_list_data()
    return Response({"data": out, "count": len(out)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def global_audit_logs(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    qs = AuditLog.objects.all().select_related("user", "hospital").order_by("-timestamp")[:500]
    return Response({
        "data": [
            {
                "log_id": str(log.id),
                "user": log.user.full_name,
                "action": log.action,
                "resource_type": log.resource_type,
                "timestamp": log.timestamp.isoformat(),
                "ip_address": str(log.ip_address),
                "hospital": log.hospital.name if log.hospital else None,
            }
            for log in qs
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def system_health(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    return Response({
        "uptime": "ok",
        "database": "ok",
        "hospitals_count": Hospital.objects.count(),
        "users_count": User.objects.count(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def break_glass_list_global(request):
    """List all break-glass events in last 30 days. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    cutoff = timezone.now() - timedelta(days=30)
    cutoff_7d = timezone.now() - timedelta(days=7)
    
    reviewed_q = request.query_params.get("reviewed")
    filters = {"created_at__gte": cutoff}
    if reviewed_q is not None:
        if reviewed_q.lower() in ("true", "1", "yes"):
            filters["reviewed"] = True
        elif reviewed_q.lower() in ("false", "0", "no"):
            filters["reviewed"] = False

    # Single query with select_related (no N+1)
    logs = (
        BreakGlassLog.objects.filter(**filters)
        .select_related("global_patient", "facility", "accessed_by")
        .order_by("-created_at")[:200]
    )
    
    data = [
        {
            "break_glass_id": str(log.id),
            "user_name": log.accessed_by.full_name if log.accessed_by else "",
            "user_email": log.accessed_by.email if log.accessed_by else "",
            "hospital_name": log.facility.name if log.facility else "",
            "hospital_id": str(log.facility_id),
            "patient_name": log.global_patient.full_name if log.global_patient else "",
            "global_patient_id": str(log.global_patient_id),
            "reason": log.reason,
            "created_at": log.created_at.isoformat(),
            "reviewed": bool(getattr(log, "reviewed", False)),
            "excessive_usage": bool(getattr(log, "excessive_usage", False)),
        }
        for log in logs
    ]
    
    # Single query for 7-day summary (no duplicate query)
    summary_7d = {
        "total": BreakGlassLog.objects.filter(created_at__gte=cutoff_7d).count(),
        "unreviewed": BreakGlassLog.objects.filter(created_at__gte=cutoff_7d, reviewed=False).count(),
    }
    
    return Response({"data": data, "count": len(data), "summary_7d": summary_7d})



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def break_glass_mark_reviewed(request, break_glass_id):
    denied = _require_super_admin(request)
    if denied:
        return denied
    try:
        log = BreakGlassLog.objects.get(id=break_glass_id)
    except BreakGlassLog.DoesNotExist:
        return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    log.reviewed = True
    log.reviewed_at = timezone.now()
    log.reviewed_by = request.user
    log.save(update_fields=["reviewed", "reviewed_at", "reviewed_by"])
    return Response({"status": "ok", "break_glass_id": str(log.id), "reviewed": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def break_glass_flag_abuse(request, break_glass_id):
    denied = _require_super_admin(request)
    if denied:
        return denied
    try:
        log = BreakGlassLog.objects.get(id=break_glass_id)
    except BreakGlassLog.DoesNotExist:
        return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    log.excessive_usage = True
    log.save(update_fields=["excessive_usage"])
    return Response({"status": "ok", "break_glass_id": str(log.id), "excessive_usage": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gmdc_unverified_doctors(request):
    """List doctors with unverified GMDC licence. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    users = User.objects.filter(role="doctor", licence_verified=False).exclude(gmdc_licence_number__isnull=True).exclude(gmdc_licence_number="").select_related("hospital").order_by("full_name")[:100]
    data = [
        {
            "user_id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "gmdc_licence_number": u.gmdc_licence_number or "",
            "hospital_name": u.hospital.name if u.hospital else None,
        }
        for u in users
    ]
    return Response({"data": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def onboard_hospital(request):
    """Create a new hospital. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    data = request.data
    name = (data.get("name") or "").strip()
    region = (data.get("region") or "").strip()
    nhis_code = (data.get("nhis_code") or "").strip()
    if not name or not region or not nhis_code:
        return Response(
            {"message": "name, region, and nhis_code required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if Hospital.objects.filter(nhis_code=nhis_code).exists():
        return Response(
            {"message": "Hospital with this NHIS code already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    hospital = Hospital.objects.create(
        name=name,
        region=region,
        nhis_code=nhis_code,
        address=(data.get("address") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        head_of_facility=(data.get("head_of_facility") or "").strip(),
        onboarded_by=request.user,
    )
    return Response(
        {"hospital_id": str(hospital.id), "name": hospital.name, "message": "Hospital created"},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_hospital_access(request):
    """Grant a super admin explicit view-as access to a hospital."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    super_admin_id = request.data.get("super_admin_id")
    hospital_id = request.data.get("hospital_id")
    if not super_admin_id or not hospital_id:
        return Response(
            {"message": "super_admin_id and hospital_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    super_admin = User.objects.filter(id=super_admin_id, role="super_admin").first()
    if not super_admin:
        return Response({"message": "Super admin not found"}, status=status.HTTP_404_NOT_FOUND)
    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    access, created = SuperAdminHospitalAccess.objects.get_or_create(
        super_admin=super_admin,
        hospital=hospital,
        defaults={"granted_by": request.user},
    )
    audit_log(
        request.user,
        "VIEW_AS_HOSPITAL_GRANT",
        resource_type="super_admin_hospital_access",
        resource_id=access.id,
        hospital=hospital,
        request=request,
        extra_data={"super_admin_id": str(super_admin.id), "created": created},
    )
    return Response(
        {
            "super_admin_id": str(super_admin.id),
            "hospital_id": str(hospital.id),
            "granted": True,
            "created": created,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


# PHASE 6: Enhanced Hospital Onboarding Dashboard


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hospital_onboarding_dashboard(request):
    """Hospital onboarding dashboard with metrics and connectivity. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    
    hospitals = Hospital.objects.all()
    data = []
    
    for hospital in hospitals:
        user_count = User.objects.filter(hospital=hospital).count()
        doctor_count = User.objects.filter(hospital=hospital, role="doctor").count()
        nurse_count = User.objects.filter(hospital=hospital, role="nurse").count()
        
        # Interoperability metrics
        facility_links = FacilityPatient.objects.filter(facility=hospital, deleted_at__isnull=True).values_list('global_patient', flat=True).distinct().count()
        consents_granted = Consent.objects.filter(granted_to_facility=hospital, is_active=True).count()
        referrals_received = Referral.objects.filter(to_facility=hospital, status__in=['accepted', 'completed']).count()
        
        data.append({
            "hospital_id": str(hospital.id),
            "name": hospital.name,
            "nhis_code": hospital.nhis_code,
            "region": hospital.region,
            "is_active": hospital.is_active,
            "created_at": hospital.created_at.isoformat() if hospital.created_at else None,
            "staff": {
                "total": user_count,
                "doctors": doctor_count,
                "nurses": nurse_count,
                "others": user_count - doctor_count - nurse_count,
            },
            "interop": {
                "cross_facility_patients": facility_links,
                "active_consents": consents_granted,
                "referrals_received": referrals_received,
            }
        })
    
    return Response({
        "hospitals": data,
        "total_hospitals": len(data),
        "total_active": sum(1 for h in data if h["is_active"]),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def bulk_import_staff(request, hospital_id):
    """Bulk import staff from CSV. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except (Hospital.DoesNotExist, ValueError):
        return Response(
            {"message": "Hospital not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    if "csv_file" not in request.FILES:
        return Response(
            {"message": "csv_file required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    csv_file = request.FILES["csv_file"]
    try:
        file_content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(file_content))
        
        created = []
        errors = []
        
        for idx, row in enumerate(reader, start=2):
            try:
                email = (row.get("email") or "").strip()
                full_name = (row.get("full_name") or "").strip()
                role = (row.get("role") or "").strip()
                ward_name = (row.get("ward") or "").strip()
                
                if not email or not full_name or not role:
                    errors.append(f"Row {idx}: Missing required fields (email, full_name, role)")
                    continue
                
                if User.objects.filter(email=email).exists():
                    errors.append(f"Row {idx}: User {email} already exists")
                    continue
                
                if role not in ["doctor", "nurse", "lab_technician", "receptionist", "hospital_admin"]:
                    errors.append(f"Row {idx}: Invalid role '{role}'")
                    continue
                
                user = User.objects.create_user(
                    email=email,
                    full_name=full_name,
                    role=role,
                    hospital=hospital,
                )
                
                # Assign to ward if specified
                if ward_name and role in ["nurse", "doctor"]:
                    ward = Ward.objects.filter(hospital=hospital, ward_name__icontains=ward_name).first()
                    if ward:
                        user.ward = ward
                        user.save()
                
                created.append({
                    "user_id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                })
                
                # Audit log
                audit_log(
                    request.user,
                    "BULK_IMPORT_USER",
                    resource_type="user",
                    resource_id=user.id,
                    hospital=hospital,
                    request=request,
                    extra_data={"email": email, "role": role},
                )
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
        
        return Response({
            "created": created,
            "errors": errors,
            "summary": {
                "total_processed": idx,
                "created_count": len(created),
                "error_count": len(errors),
            }
        })
    
    except Exception as e:
        return Response(
            {"message": f"CSV processing error: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hospital_interop_connectivity(request, hospital_id):
    """View hospital's interoperability connections. Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except (Hospital.DoesNotExist, ValueError):
        return Response(
            {"message": "Hospital not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Shared patients
    outgoing_patients = FacilityPatient.objects.filter(
        facility=hospital, deleted_at__isnull=True
    ).values('global_patient__id').distinct().count()
    
    # Incoming consents (patients giving permission to this hospital)
    incoming_consents = Consent.objects.filter(
        granted_to_facility=hospital, is_active=True
    ).values('global_patient__id').distinct().count()
    
    # Referrals
    outgoing_referrals = Referral.objects.filter(
        from_facility=hospital, status='completed'
    ).count()
    incoming_referrals = Referral.objects.filter(
        to_facility=hospital, status='accepted'
    ).count()
    
    # Break glass events
    break_glass_count = BreakGlassLog.objects.filter(
        facility=hospital,
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    return Response({
        "hospital_id": str(hospital.id),
        "hospital_name": hospital.name,
        "connectivity": {
            "shared_patients": outgoing_patients,
            "incoming_consents": incoming_consents,
            "outgoing_referrals": outgoing_referrals,
            "incoming_referrals": incoming_referrals,
            "break_glass_last_30_days": break_glass_count,
        },
        "status": "connected" if (incoming_consents or outgoing_patients) > 0 else "isolated",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cross_facility_activity_log(request):
    """View all cross-facility activity (referrals, consents, break-glass). Super_admin only."""
    denied = _require_super_admin(request)
    if denied:
        return denied
    
    # Fetch recent activities
    days = int(request.GET.get("days", 30))
    cutoff = timezone.now() - timedelta(days=days)
    
    # Consents granted/revoked
    consents = Consent.objects.filter(created_at__gte=cutoff).select_related(
        'global_patient', 'granted_to_facility'
    ).values(
        'id', 'created_at', 'global_patient__full_name', 'granted_to_facility__name', 'scope'
    ).order_by('-created_at')[:100]
    
    # Referrals created
    referrals = Referral.objects.filter(created_at__gte=cutoff).select_related(
        'global_patient', 'from_facility', 'to_facility'
    ).values(
        'id', 'created_at', 'global_patient__full_name', 'from_facility__name', 
        'to_facility__name', 'status'
    ).order_by('-created_at')[:100]
    
    # Break glass events
    break_glass = BreakGlassLog.objects.filter(created_at__gte=cutoff).select_related(
        'global_patient', 'facility', 'accessed_by'
    ).values(
        'id', 'created_at', 'global_patient__full_name', 'facility__name', 
        'accessed_by__full_name', 'reason'
    ).order_by('-created_at')[:100]
    
    return Response({
        "consents": list(consents),
        "referrals": list(referrals),
        "break_glass_events": list(break_glass),
        "period_days": days,
        "summary": {
            "total_consents": Consent.objects.filter(created_at__gte=cutoff).count(),
            "total_referrals": Referral.objects.filter(created_at__gte=cutoff).count(),
            "total_break_glass": BreakGlassLog.objects.filter(created_at__gte=cutoff).count(),
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_chain_integrity_status(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    # Fast-ish bounded validation for dashboard display
    try:
        out = _compute_audit_chain_status(max_users=200, max_logs_per_user=500)
        return Response({k: out.get(k) for k in ("status", "last_checked_at", "message")})
    except Exception as e:
        return Response({"status": "unknown", "last_checked_at": None, "message": str(e)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def audit_chain_integrity_validate(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    # Deeper bounded validation (still bounded to avoid request timeouts)
    try:
        out = _compute_audit_chain_status(max_users=500, max_logs_per_user=2000)
        return Response({k: out.get(k) for k in ("status", "last_checked_at", "message")})
    except Exception as e:
        return Response({"status": "unknown", "last_checked_at": None, "message": str(e)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hospital_onboarding_status(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    hospital_id = request.GET.get("hospital_id")
    if not hospital_id:
        return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Exception:
        return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)

    from patients.models import Patient

    checks = [
        ("Wards created", Ward.objects.filter(hospital=hospital).exists()),
        ("Departments created", Department.objects.filter(hospital=hospital).exists()),
        ("Lab units created", LabUnit.objects.filter(hospital=hospital).exists()),
        ("First patient registered", Patient.objects.filter(registered_at=hospital).exists()),
        ("First doctor onboarded", User.objects.filter(hospital=hospital, role="doctor").exists()),
    ]
    done = [name for (name, ok) in checks if ok]
    missing = [name for (name, ok) in checks if not ok]
    completion = int(round((len(done) / len(checks)) * 100))
    return Response({
        "hospital_id": str(hospital.id),
        "completion_pct": completion,
        "missing_items": missing,
    })


def _compliance_alerts_data():
    alerts = []

    # 1) Break-glass overuse (last 7 days): hospitals above a threshold
    cutoff_7d = timezone.now() - timedelta(days=7)
    try:
        from django.db.models import Count
        bg_counts = (
            BreakGlassLog.objects.filter(created_at__gte=cutoff_7d)
            .values("facility_id", "facility__name")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")[:5]
        )
        if bg_counts:
            top = list(bg_counts)
            if top and top[0]["cnt"] >= 10:
                alerts.append({
                    "id": "break_glass_overuse_7d",
                    "severity": "warning" if top[0]["cnt"] < 25 else "critical",
                    "title": "Break-glass overuse (7d)",
                    "detail": ", ".join([f"{r['facility__name']}: {r['cnt']}" for r in top]),
                })
    except Exception:
        pass

    # 2) Expired consent still active
    now = timezone.now()
    expired_active = Consent.objects.filter(is_active=True, expires_at__isnull=False, expires_at__lt=now).count()
    if expired_active > 0:
        alerts.append({
            "id": "expired_consent_active",
            "severity": "critical",
            "title": "Expired consent still active",
            "detail": f"{expired_active} consent(s) are active past expiry.",
        })

    # 3) Referrals pending > 7 days
    cutoff_7d_ref = timezone.now() - timedelta(days=7)
    pending_ref = Referral.objects.filter(created_at__lt=cutoff_7d_ref).exclude(status__in=["accepted", "completed"]).count()
    if pending_ref > 0:
        alerts.append({
            "id": "referral_pending_gt_7d",
            "severity": "warning",
            "title": "Referrals pending > 7 days",
            "detail": f"{pending_ref} referral(s) pending longer than 7 days.",
        })

    # 4) Hospitals with no patients registered
    try:
        from patients.models import Patient
        zero_patient_hospitals = Hospital.objects.filter(is_active=True).exclude(
            id__in=Patient.objects.values_list("registered_at_id", flat=True).distinct()
        )[:20]
        if zero_patient_hospitals.exists():
            alerts.append({
                "id": "hospitals_no_patients",
                "severity": "info",
                "title": "Hospitals with no patients registered",
                "detail": ", ".join([h.name for h in zero_patient_hospitals]),
            })
    except Exception:
        pass

    return alerts


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compliance_alerts(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    return Response({"data": _compliance_alerts_data()})


def _global_audit_logs_preview(limit: int = 5):
    qs = AuditLog.objects.all().select_related("user", "hospital").order_by("-timestamp")[:limit]
    return [
        {
            "log_id": str(log.id),
            "user": log.user.full_name,
            "action": log.action,
            "resource_type": log.resource_type,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": str(log.ip_address),
            "hospital": log.hospital.name if log.hospital else None,
        }
        for log in qs
    ]


def _break_glass_summary_7d():
    cutoff_7d = timezone.now() - timedelta(days=7)
    qs_7d = BreakGlassLog.objects.filter(created_at__gte=cutoff_7d)
    return {
        "total": qs_7d.count(),
        "unreviewed": qs_7d.filter(reviewed=False).count(),
    }


def _pending_admin_grants_payload(request):
    hosp_admin_hospital_ids = set(
        User.objects.filter(role="hospital_admin", account_status__in=["pending", "active"])
        .exclude(hospital_id__isnull=True)
        .values_list("hospital_id", flat=True)
    )
    hospitals_no_admin = Hospital.objects.exclude(id__in=hosp_admin_hospital_ids).order_by("name")[:200]

    pending_admin_invites = (
        User.objects.filter(
            role="hospital_admin",
            account_status="pending",
            invited_by=request.user,
        )
        .select_related("hospital")
        .order_by("-created_at")[:200]
    )

    now = timezone.now()
    grants = (
        SuperAdminHospitalAccess.objects.filter(accepted_at__isnull=True)
        .select_related("hospital", "super_admin")
        .order_by("-granted_at")[:200]
    )

    return {
        "hospitals_no_admin": [
            {
                "hospital_id": str(h.id),
                "hospital_name": h.name,
                "created_at": h.onboarded_at.isoformat() if h.onboarded_at else None,
            }
            for h in hospitals_no_admin
        ],
        "pending_invites": [
            {
                "user_id": str(u.id),
                "email": u.email,
                "hospital_id": str(u.hospital_id) if u.hospital_id else None,
                "hospital_name": u.hospital.name if u.hospital else None,
                "sent_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
                "expires_at": u.invitation_expires_at.isoformat() if u.invitation_expires_at else None,
                "expires_soon": bool(u.invitation_expires_at and (u.invitation_expires_at - now) <= timedelta(days=2)),
            }
            for u in pending_admin_invites
        ],
        "pending_grants": [
            {
                "access_id": str(a.id),
                "super_admin_email": a.super_admin.email if a.super_admin else "",
                "hospital_id": str(a.hospital_id),
                "hospital_name": a.hospital.name if a.hospital else "",
                "sent_at": a.granted_at.isoformat() if a.granted_at else None,
                "accepted_at": None,
            }
            for a in grants
        ],
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_hospital_admin_assignments(request):
    """
    Super Admin dashboard panel:
    - Hospitals with no hospital_admin (pending or active)
    - Pending hospital_admin invites initiated by super_admin
    - View-as grants created but not yet accepted (accepted_at is null)
    """
    denied = _require_super_admin(request)
    if denied:
        return denied

    # Hospitals with no assigned hospital admin (pending or active)
    hosp_admin_hospital_ids = set(
        User.objects.filter(role="hospital_admin", account_status__in=["pending", "active"])
        .exclude(hospital_id__isnull=True)
        .values_list("hospital_id", flat=True)
    )
    hospitals_no_admin = Hospital.objects.exclude(id__in=hosp_admin_hospital_ids).order_by("name")[:200]

    # Pending invites created by this super_admin (hospital_admin role only)
    pending_admin_invites = (
        User.objects.filter(
            role="hospital_admin",
            account_status="pending",
            invited_by=request.user,
        )
        .select_related("hospital")
        .order_by("-created_at")[:100]
    )

    # View-as grants created but not yet accepted
    pending_grants = (
        SuperAdminHospitalAccess.objects.select_related("hospital", "super_admin")
        .filter(accepted_at__isnull=True)
        .order_by("-granted_at")[:200]
    )

    return Response(
        {
            "hospitals_no_admin": [
                {
                    "hospital_id": str(h.id),
                    "hospital_name": h.name,
                }
                for h in hospitals_no_admin
            ],
            "pending_admin_invites": [
                {
                    "user_id": str(u.id),
                    "email": u.email,
                    "full_name": u.full_name,
                    "hospital_id": str(u.hospital_id) if u.hospital_id else None,
                    "hospital_name": u.hospital.name if u.hospital else None,
                    "sent_at": u.created_at.isoformat() if u.created_at else None,
                    "expires_at": u.invitation_expires_at.isoformat() if u.invitation_expires_at else None,
                }
                for u in pending_admin_invites
            ],
            "pending_view_as_grants": [
                {
                    "access_id": str(a.id),
                    "hospital_id": str(a.hospital_id),
                    "hospital_name": a.hospital.name if a.hospital else "",
                    "super_admin_email": a.super_admin.email if a.super_admin else "",
                    "sent_at": a.granted_at.isoformat() if a.granted_at else None,
                }
                for a in pending_grants
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_admin_grants(request):
    """
    Spec-oriented endpoint:
    - Hospitals with no hospital_admin assigned
    - Pending hospital_admin invites initiated by this super_admin (near expiry flagged)
    - SuperAdminHospitalAccess grants not accepted (accepted_at null)
    """
    denied = _require_super_admin(request)
    if denied:
        return denied
    return Response(_pending_admin_grants_payload(request))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def superadmin_dashboard_bundle(request):
    """
    Single response for Super Admin home dashboard: health, AI status, hospitals,
    onboarding, compliance, pending grants, audit preview, break-glass 7d summary.
    Reduces parallel HTTP calls and timeouts on slow networks.
    """
    denied = _require_super_admin(request)
    if denied:
        return denied
    from api.views.health_views import build_health_payload
    from api.views.ai_views import build_ai_status_payload

    health_payload, _db_ok = build_health_payload(deep=True)
    hospitals_data = _hospitals_list_data()
    onboarding_data = _hospital_onboarding_list_data()
    compliance = _compliance_alerts_data()
    pending_dict = _pending_admin_grants_payload(request)
    audit_preview = _global_audit_logs_preview(5)
    bg7 = _break_glass_summary_7d()

    return Response(
        {
            "generated_at": timezone.now().isoformat(),
            "health": health_payload,
            "ai_status": build_ai_status_payload(),
            "hospitals": {"data": hospitals_data, "count": len(hospitals_data)},
            "onboarding": {"data": onboarding_data, "count": len(onboarding_data)},
            "compliance_alerts": {"data": compliance},
            "pending_admin_grants": pending_dict,
            "audit_logs_preview": {"data": audit_preview},
            "break_glass_summary_7d": bg7,
        }
    )
