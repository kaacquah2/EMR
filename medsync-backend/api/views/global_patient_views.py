import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

logger = logging.getLogger(__name__)

from core.models import Hospital
from interop.models import GlobalPatient, FacilityPatient, SharedRecordAccess, Consent, Referral, BreakGlassLog
from api.utils import (
    get_global_patient_queryset,
    can_access_cross_facility,
    get_effective_hospital,
    get_request_hospital,
    audit_log
)
from api.serializers import GlobalPatientSerializer, FacilityPatientSerializer


def _interop_role_ok(user):
    return user.role in ("doctor", "hospital_admin", "super_admin")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def global_patient_search(request):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    query = (request.GET.get("query") or request.GET.get("q") or "").strip()
    date_of_birth = request.GET.get("date_of_birth") or request.GET.get("dob")
    if not query and not date_of_birth:
        return Response({"data": [], "next_cursor": None, "has_more": False})

    qs = get_global_patient_queryset(request.user, get_effective_hospital(request))
    if query:
        qs = qs.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(national_id__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    if date_of_birth:
        from django.utils.dateparse import parse_date
        dob = parse_date(date_of_birth)
        if dob:
            qs = qs.filter(date_of_birth=dob)
    qs = qs.distinct()[:50]
    # Annotate with facility names where this global patient is linked
    out = []
    for gp in qs:
        d = GlobalPatientSerializer(gp).data
        facilities = FacilityPatient.objects.filter(
            global_patient=gp, deleted_at__isnull=True
        ).select_related("facility")
        d["facility_ids"] = [str(fp.facility_id) for fp in facilities]
        d["facility_names"] = [fp.facility.name for fp in facilities]
        out.append(d)
    return Response({"data": out, "next_cursor": None, "has_more": False})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def facility_patient_link(request):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.user.role == "super_admin" and not hospital and request.data.get("facility_id"):
        fid = request.data.get("facility_id")
        try:
            hospital = Hospital.objects.get(id=fid)
        except (Hospital.DoesNotExist, ValueError):
            return Response(
                {"message": "Invalid facility_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    if not hospital:
        return Response(
            {"message": "facility_id required for super_admin"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    global_patient_id = request.data.get("global_patient_id")
    local_patient_id = (request.data.get("local_patient_id") or "").strip()
    if not global_patient_id:
        return Response(
            {"message": "global_patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if FacilityPatient.objects.filter(
        facility=hospital, global_patient=gp, deleted_at__isnull=True
    ).exists():
        return Response(
            {"message": "Patient already linked to this facility"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from patients.models import Patient

    patient = None
    if local_patient_id:
        try:
            patient = Patient.objects.get(
                id=local_patient_id, registered_at=hospital
            )
        except (Patient.DoesNotExist, ValueError):
            logger.debug(f"Patient {local_patient_id} not found in hospital {hospital.id} for global registry link")
    if not local_patient_id:
        local_patient_id = str(gp.id)

    fp = FacilityPatient.objects.create(
        facility=hospital,
        global_patient=gp,
        local_patient_id=local_patient_id,
        patient=patient,
    )
    return Response(
        FacilityPatientSerializer(fp).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def facilities_list(request):
    """List facilities (GET). Create facility (POST, super_admin only)."""
    if request.method == "GET":
        if not _interop_role_ok(request.user):
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Super admin sees only hospitals they have explicit access to
        if request.user.role == "super_admin":
            from core.models import SuperAdminHospitalAccess
            hospital_ids = SuperAdminHospitalAccess.objects.filter(
                super_admin=request.user
            ).values_list('hospital_id', flat=True)
            hospitals = Hospital.objects.filter(
                id__in=hospital_ids,
                is_active=True
            ).order_by("name")
        # Other roles (doctor, hospital_admin) see only their own hospital
        elif request.user.role in ("doctor", "hospital_admin"):
            if request.user.hospital_id:
                hospitals = Hospital.objects.filter(id=request.user.hospital_id)
            else:
                hospitals = Hospital.objects.none()
        else:
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = [
            {
                "facility_id": str(h.id),
                "name": h.name,
                "region": h.region,
                "nhis_code": h.nhis_code,
                "address": h.address or "",
                "phone": h.phone or "",
                "email": h.email or "",
                "is_active": h.is_active,
            }
            for h in hospitals
        ]
        return Response({"data": data})
    if request.method == "POST":
        if request.user.role != "super_admin":
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data
        name = (data.get("name") or "").strip()
        nhis_code = (data.get("nhis_code") or "").strip()
        if not name or not nhis_code:
            return Response(
                {"message": "name and nhis_code required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Hospital.objects.filter(nhis_code=nhis_code).exists():
            return Response(
                {"message": "Facility with this NHIS code already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hospital = Hospital.objects.create(
            name=name,
            region=(data.get("region") or "").strip() or "Unknown",
            nhis_code=nhis_code,
            address=(data.get("address") or "").strip() or "",
            phone=(data.get("phone") or "").strip() or "",
            email=(data.get("email") or "").strip() or "",
            head_of_facility=(data.get("head_of_facility") or "").strip() or "",
        )
        return Response(
            {
                "facility_id": str(hospital.id),
                "name": hospital.name,
                "region": hospital.region,
                "nhis_code": hospital.nhis_code,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def facility_update(request, pk):
    """Update facility (super_admin only)."""
    if request.user.role != "super_admin":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        hospital = Hospital.objects.get(id=pk)
    except (Hospital.DoesNotExist, ValueError):
        return Response(
            {"message": "Facility not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    data = request.data
    if "name" in data and data["name"] is not None:
        hospital.name = (data["name"] or "").strip()
    if "region" in data and data["region"] is not None:
        hospital.region = (data["region"] or "").strip()
    if "nhis_code" in data and data["nhis_code"] is not None:
        hospital.nhis_code = (data["nhis_code"] or "").strip()
    if "address" in data:
        hospital.address = (data["address"] or "").strip()
    if "phone" in data:
        hospital.phone = (data["phone"] or "").strip()
    if "email" in data:
        hospital.email = (data["email"] or "").strip()
    if "head_of_facility" in data:
        hospital.head_of_facility = (data["head_of_facility"] or "").strip()
    if "is_active" in data and data["is_active"] is not None:
        hospital.is_active = bool(data["is_active"])
    hospital.save()
    return Response({
        "facility_id": str(hospital.id),
        "name": hospital.name,
        "region": hospital.region,
        "nhis_code": hospital.nhis_code,
        "is_active": hospital.is_active,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cross_facility_records(request, global_patient_id):
    """
    Read-only aggregated records for a global patient. Requires consent,
    accepted referral, or recent break-glass (enforced server-side).
    """
    from interop.models import FacilityPatient
    from records.models import MedicalRecord
    from api.serializers import (
        GlobalPatientSerializer,
        MedicalRecordSerializer,
    )

    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    allowed, scope = can_access_cross_facility(
        request.user, global_patient_id, allow_break_glass=True, effective_hospital=get_effective_hospital(request)
    )
    if not allowed:
        return Response(
            {"message": "No consent, accepted referral, or break-glass access for this patient"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # -----------------------------------------------------------------------
    # DATA RESIDENCY ENFORCEMENT (NDPA 2012 § 36 / Ghana Data Protection Act)
    # -----------------------------------------------------------------------
    if gp.data_residency_locked:
        requesting_hospital = get_request_hospital(request)
        is_super_admin = request.user.role == "super_admin"

        # Hospital.country is a real CharField (default "GH") — migration 0042.
        # Previously read a non-existent attribute (country_code) which always
        # defaulted to "GH", making the residency check a no-op.
        facility_country = getattr(requesting_hospital, "country", "GH") if requesting_hospital else "GH"

        if facility_country != gp.data_residency_country and not is_super_admin:
            # Log the denied access attempt
            audit_log(
                request.user,
                "PERMISSION_DENIED",
                resource_type="global_patient",
                resource_id=global_patient_id,
                hospital=requesting_hospital,
                request=request,
                extra_data={
                    "reason": "data_residency_restriction",
                    "patient_residency": gp.data_residency_country,
                    "facility_country": facility_country,
                },
            )
            return Response(
                {
                    "message": (
                        f"Access denied: Patient data is restricted to facilities in "
                        f"'{gp.data_residency_country}' (Ghana Data Protection Act / NDPA 2012 § 36). "
                        f"Contact a super admin if you believe this is an error."
                    ),
                    "data_residency_country": gp.data_residency_country,
                    "error_code": "DATA_RESIDENCY_RESTRICTION",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Super-admin override — log it prominently for compliance audit
        if is_super_admin and facility_country != gp.data_residency_country:
            audit_log(
                request.user,
                "CROSS_FACILITY_ACCESS",
                resource_type="global_patient",
                resource_id=global_patient_id,
                hospital=requesting_hospital,
                request=request,
                extra_data={
                    "reason": "super_admin_data_residency_override",
                    "patient_residency": gp.data_residency_country,
                    "facility_country": facility_country,
                },
            )



    # If access is via break-glass, find the expiry
    expires_at = None
    if scope == "FULL_RECORD":
        from django.utils import timezone
        hospital = get_request_hospital(request)
        bg_log = BreakGlassLog.objects.filter(
            global_patient=gp,
            facility=hospital,
            accessed_by=request.user,
            expires_at__gt=timezone.now()
        ).order_by("-expires_at").first()
        if bg_log:
            expires_at = bg_log.expires_at.isoformat()

    try:
        from uuid import UUID
        if isinstance(global_patient_id, UUID):
            rid = global_patient_id
        else:
            rid = UUID(global_patient_id)
    except (ValueError, TypeError):
        rid = None
    audit_log(
        request.user,
        "VIEW_CROSS_FACILITY_RECORD",
        resource_type="global_patient",
        resource_id=rid,
        hospital=get_request_hospital(request),
        request=request,
        extra_data={"scope": scope},
    )
    SharedRecordAccess.objects.create(
        global_patient=gp,
        accessing_facility=get_request_hospital(request),
        accessed_by=request.user,
        scope=scope,
    )

    demographics = GlobalPatientSerializer(gp).data
    facility_profiles = FacilityPatient.objects.filter(
        global_patient=gp, deleted_at__isnull=True
    ).select_related("facility", "patient")
    patient_ids = [fp.patient_id for fp in facility_profiles if fp.patient_id]

    if scope == "SUMMARY" or not patient_ids:
        return Response({
            "demographics": demographics,
            "scope": scope,
            "facilities": [
                {"facility_id": str(fp.facility_id), "name": fp.facility.name}
                for fp in facility_profiles
            ],
            "records": [],
            "read_only": True,
            "expires_at": expires_at,
        })

    # -----------------------------------------------------------------------
    # Granular consent enforcement (NDPA 2012 — data minimisation principle)
    # -----------------------------------------------------------------------
    # Retrieve the active consent for this facility so we can apply any
    # per-record or category exclusions the patient has set.
    from django.utils import timezone as _tz
    from django.db.models import Q as _Q
    active_consent = (
        Consent.objects.filter(
            global_patient=gp,
            granted_to_facility=get_request_hospital(request),
            is_active=True,
        )
        .filter(_Q(expires_at__isnull=True) | _Q(expires_at__gt=_tz.now()))
        .prefetch_related("excluded_scopes")
        .order_by("-created_at")
        .first()
    )

    records_qs = (
        MedicalRecord.objects.filter(patient_id__in=patient_ids)
        .select_related("patient", "hospital", "diagnosis", "prescription", "vital", "labresult")
        .order_by("-created_at")
    )

    if active_consent:
        # 1) Per-record allow-list: if the patient specified exact record IDs
        #    to share, restrict to those only.
        consented_ids = active_consent.consented_record_ids
        if consented_ids:
            records_qs = records_qs.filter(id__in=consented_ids)

        # 2) Excluded clinical categories (e.g. HIV, MentalHealth).
        #    MedicalRecord has a `category` field (or falls back to record_type).
        excluded_categories = list(
            active_consent.excluded_scopes.values_list("name", flat=True)
        )
        if excluded_categories:
            # Filter out records whose category matches any excluded scope name.
            # `category` on MedicalRecord is a CharField; fall back to record_type.
            category_field = "category" if hasattr(MedicalRecord, "category") else "record_type"
            records_qs = records_qs.exclude(**{f"{category_field}__in": excluded_categories})

    records = records_qs[:200]
    records_data = MedicalRecordSerializer(records, many=True).data

    # Build a list of active exclusions to surface in the response so the UI
    # can display "Some categories excluded by patient" rather than confusion.
    excluded_labels = []
    if active_consent:
        excluded_labels = list(
            active_consent.excluded_scopes.values_list("name", flat=True)
        )

    return Response({
        "demographics": demographics,
        "scope": scope,
        "facilities": [
            {"facility_id": str(fp.facility_id), "name": fp.facility.name}
            for fp in facility_profiles
        ],
        "records": records_data,
        "read_only": True,
        "expires_at": expires_at,
        "excluded_categories": excluded_labels,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def accessible_patients(request):
    """
    List global patients the current facility has cross-facility access to via:
    1. Active Consent
    2. Accepted/Completed Referral
    3. Recent Break-Glass
    """
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"data": []})

    from django.utils import timezone
    from datetime import timedelta
    from api.utils import BREAK_GLASS_VALID_MINUTES

    now = timezone.now()
    
    # 1. Patients with active consent
    consent_gp_ids = Consent.objects.filter(
        granted_to_facility=hospital,
        is_active=True
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).values_list('global_patient_id', flat=True)

    # 2. Patients with accepted/completed referral
    referral_gp_ids = Referral.objects.filter(
        to_facility=hospital,
        status__in=(Referral.STATUS_ACCEPTED, Referral.STATUS_COMPLETED)
    ).values_list('global_patient_id', flat=True)

    # 3. Recent break-glass by the user
    cutoff = now - timedelta(minutes=BREAK_GLASS_VALID_MINUTES)
    break_glass_gp_ids = BreakGlassLog.objects.filter(
        facility=hospital,
        accessed_by=request.user,
        created_at__gte=cutoff
    ).values_list('global_patient_id', flat=True)

    # Combine all IDs
    all_gp_ids = set(list(consent_gp_ids) + list(referral_gp_ids) + list(break_glass_gp_ids))
    
    if not all_gp_ids:
        return Response({"data": []})

    # Fetch GlobalPatient records
    qs = GlobalPatient.objects.filter(id__in=all_gp_ids).order_by("-updated_at")
    
    out = []
    for gp in qs:
        d = GlobalPatientSerializer(gp).data
        # Add access reasons
        reasons = []
        if gp.id in consent_gp_ids: reasons.append("CONSENT")
        if gp.id in referral_gp_ids: reasons.append("REFERRAL")
        if gp.id in break_glass_gp_ids: reasons.append("BREAK_GLASS")
        d["access_reasons"] = reasons
        out.append(d)

    return Response({"data": out})
