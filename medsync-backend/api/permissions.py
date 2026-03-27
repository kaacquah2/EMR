"""
Permission enforcement middleware for MedSync API.

This middleware:
1. Validates all incoming requests against role-based permissions
2. Logs all permission denials and failures
3. Tracks permission metrics by endpoint, role, and action
4. Provides centralized permission validation for audit compliance
"""

import json
import logging
from typing import Optional
from functools import wraps
from django.conf import settings
from django.http import JsonResponse
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from core.models import AuditLog

logger = logging.getLogger(__name__)

# Single source of truth for alert resolution access.
ALERT_RESOLVE_ROLES = {"doctor", "nurse"}

def _dev_bypass_emails() -> set[str]:
    """
    Dev-only escape hatch to unblock local workflows.
    Never enable in production (guarded by DEBUG).
    """
    raw = getattr(settings, "DEV_PERMISSION_BYPASS_EMAILS", []) or []
    # Settings may provide a list or a comma-separated string.
    if isinstance(raw, str):
        items = [p.strip().lower() for p in raw.split(",") if p.strip()]
        return set(items)
    try:
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    except TypeError:
        return set()


# Permission matrix: endpoint -> {role -> [allowed_methods]}
# This is the source of truth for what each role can do
PERMISSION_MATRIX = {
    # Health endpoint (public)
    "health": {"public": ["GET"]},

    # Auth endpoints (public)
    "auth/login": {"public": ["POST"]},
    "auth/mfa-verify": {"public": ["POST"]},
    "auth/activate": {"public": ["POST"]},
    "auth/forgot-password": {"public": ["POST"]},
    "auth/reset-password": {"public": ["POST"]},
    "auth/refresh": {"authenticated": ["POST"]},
    "auth/logout": {"authenticated": ["POST"]},
    "auth/me": {"authenticated": ["GET"]},

    # Patient endpoints
    "patients/search": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/duplicate-check": {
        "receptionist": ["GET", "POST"],
        "ward_clerk": ["GET", "POST"],
        "hospital_admin": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
    },
    "patients": {
        "receptionist": ["POST"],
        "ward_clerk": ["POST"],
        "hospital_admin": ["POST"],
    },
    "patients/<pk>": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "receptionist": ["GET"],
        "lab_technician": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET", "PUT", "PATCH"],
        "super_admin": ["GET", "PUT", "PATCH"],
    },
    "patients/<pk>/encounters": {
        "doctor": ["GET", "POST"],
        "hospital_admin": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
        "nurse": ["GET"],
    },
    "patients/<pk>/records": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/diagnoses": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/prescriptions": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "pharmacist": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/labs": {
        "doctor": ["GET"],
        "lab_technician": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/vitals": {
        "nurse": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/allergies": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "pharmacist": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },

    # Record creation endpoints (restricted)
    "records/diagnosis": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "records/prescription": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "records/prescription/<pk>/dispense": {
        "nurse": ["POST"],
        "pharmacist": ["PATCH"],
    },
    "records/prescription/<pk>/dispense-by-nurse": {
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },
    "records/lab-order": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "records/vitals": {
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },
    "records/vitals/batch": {
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },
    "records/allergy": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "records/nursing-note": {
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },

    # Admin endpoints (hospital_admin and super_admin only)
    "admin/users": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/users/invite": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/users/bulk-import": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/users/<pk>": {
        "hospital_admin": ["GET", "PUT", "PATCH"],
        "super_admin": ["GET", "PUT", "PATCH"],
    },
    "admin/audit-logs": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/wards": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/wards/occupancy": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
        "doctor": ["GET"],
        "nurse": ["GET"],
    },
    "admin/wards/create": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/wards/<pk>": {
        "hospital_admin": ["PATCH"],
        "super_admin": ["PATCH"],
    },
    "admin/wards/<pk>/beds/bulk": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/rbac-review": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/users/<pk>/role": {
        "hospital_admin": ["PATCH"],
        "super_admin": ["PATCH"],
    },
    "admin/departments": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/lab-units": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/lab-test-types": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },

    # Alerts (all clinical roles)
    "alerts": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "pharmacist": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "alerts/<pk>/resolve": {
        role: ["PATCH"] for role in ALERT_RESOLVE_ROLES
    },

    # Worklist (doctors)
    "worklist/encounters": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "worklist": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },

    # Lab endpoints
    "lab/orders": {
        "lab_technician": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "lab/orders/<pk>": {
        "lab_technician": ["GET", "PATCH"],
        "super_admin": ["GET", "PATCH"],
    },
    "lab/orders/<pk>/result": {
        "lab_technician": ["POST"],
        "super_admin": ["POST"],
    },

    # Admissions
    "admissions": {
        "nurse": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admissions/create": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admissions/<pk>/discharge": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },

    # Dashboard
    "dashboard/metrics": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "dashboard/analytics": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },

    # Appointments
    "appointments": {
        "receptionist": ["GET", "POST"],
        "doctor": ["GET", "POST"],
        "hospital_admin": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
    },
    "appointments/create": {
        "receptionist": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "appointments/check-availability": {
        "receptionist": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "dashboard": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "appointments/<pk>": {
        "receptionist": ["GET", "PUT", "PATCH"],
        "hospital_admin": ["GET", "PUT", "PATCH"],
        "super_admin": ["GET", "PUT", "PATCH"],
    },
    "appointments/<pk>/delete": {
        "receptionist": ["DELETE"],
        "hospital_admin": ["DELETE"],
        "super_admin": ["DELETE"],
    },
    "appointments/<pk>/check-in": {
        "receptionist": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "appointments/<pk>/reschedule": {
        "receptionist": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },

    # Reports
    "reports/patients/export": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "reports/audit/export": {
        "hospital_admin": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
    },
    "audit/export": {
        "hospital_admin": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
    },

    # FHIR endpoints (read-only for authorized roles)
    "fhir/Patient": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Patient/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Encounter": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Encounter/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Condition": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Condition/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/MedicationRequest": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/MedicationRequest/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Observation": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "fhir/Observation/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "hl7/adt": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "interop/fhir-push": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },

    # AI Intelligence Module (Phase 8)
    "ai/analyze-patient/<pk>": {
        "doctor": ["POST"],
        "nurse": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/risk-prediction/<pk>": {
        "doctor": ["POST"],
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/clinical-decision-support/<pk>": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/triage/<pk>": {
        "doctor": ["POST"],
        "nurse": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/find-similar-patients/<pk>": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/referral-recommendation/<pk>": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "ai/analysis-history/<pk>": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "super_admin": ["GET"],
    },
    "ai/status": {
        "super_admin": ["GET"],
    },

    # Additional auth/account flows
    "auth/activate-setup": {"public": ["GET", "POST"]},
    "auth/login-temp-password": {"public": ["POST"]},
    "auth/change-password-on-login": {"authenticated": ["POST"]},

    # Additional patient/record workflows
    "patients/<pk>/encounters/<pk>": {
        "doctor": ["GET", "PATCH"],
        "hospital_admin": ["GET", "PATCH"],
        "super_admin": ["GET", "PATCH"],
        "nurse": ["GET"],
    },
    "patients/<pk>/encounters/<pk>/close": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "records/icd10-autocomplete": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "icd10/search": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "records/drug-autocomplete": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "pharmacist": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "patients/<pk>/export-pdf": {
        "doctor": ["GET"],
        "super_admin": ["GET"],
    },
    "records/radiology-order": {
        "radiology_technician": ["GET"],
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "records/radiology-order/<pk>/attachment": {
        "doctor": ["POST"],
        "radiology_technician": ["POST"],
        "super_admin": ["POST"],
    },
    "records/<pk>/amend": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "doctor/favorites/prescriptions": {
        "doctor": ["GET", "POST"],
        "super_admin": ["GET", "POST"],
    },
    "doctor/prescriptions/<pk>/refill": {
        "doctor": ["POST"],
        "super_admin": ["POST"],
    },
    "doctor/records/<pk>/amendment-history": {
        "doctor": ["GET"],
        "super_admin": ["GET"],
    },

    # Additional admin management
    "admin/users/<pk>/send-password-reset": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/users/<pk>/reset-mfa": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/users/<pk>/resend-invite": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/staff-onboarding": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/departments/create": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/lab-units/create": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/lab-test-types/create": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/doctors": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/duplicates": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/duplicates/create": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/duplicates/<pk>": {
        "hospital_admin": ["GET", "PATCH"],
        "super_admin": ["GET", "PATCH"],
    },
    "admin/wards/<pk>/beds": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/beds": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/beds/<pk>": {
        "hospital_admin": ["PATCH"],
        "super_admin": ["PATCH"],
    },

    # Clinical/lab/admission extended workflows
    "lab/attachments/upload": {
        "lab_technician": ["POST"],
        "super_admin": ["POST"],
    },
    "admissions/ward/<pk>": {
        "nurse": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "appointments/no-show-statistics": {
        "receptionist": ["GET"],
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "appointments/<pk>/no-show": {
        "receptionist": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "appointments/<pk>/unmark-no-show": {
        "receptionist": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },

    # Reports/billing
    "billing/invoices": {
        "hospital_admin": ["GET"],
        "billing_staff": ["GET", "POST"],
        "super_admin": ["GET"],
    },
    "billing/nhis-claim": {
        "hospital_admin": ["POST"],
        "billing_staff": ["POST"],
    },

    # Interop / super-admin / nurse advanced / task endpoints
    "superadmin/dashboard-bundle": {"super_admin": ["GET"]},
    "superadmin/hospitals": {"super_admin": ["GET", "POST", "PATCH"]},
    "superadmin/audit-logs": {"super_admin": ["GET"]},
    "audit/global-logs": {"super_admin": ["GET"]},
    "audit/validate-chain": {"super_admin": ["POST"]},
    "superadmin/system-health": {"super_admin": ["GET"]},
    "superadmin/break-glass": {"super_admin": ["GET"]},
    "superadmin/break-glass-list-global": {"super_admin": ["GET"]},
    "superadmin/break-glass/<pk>/review": {"super_admin": ["POST"]},
    "superadmin/break-glass/<pk>/flag-abuse": {"super_admin": ["POST"]},
    "superadmin/grant-hospital-access": {"super_admin": ["POST"]},
    "superadmin/gmdc-unverified": {"super_admin": ["GET"]},
    "superadmin/onboard-hospital": {"super_admin": ["POST"]},
    "global-patients/search": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "facility-patients/link": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "facilities": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET", "POST"],
    },
    "facilities/<pk>": {
        "super_admin": ["PATCH"],
    },
    "cross-facility-records/<pk>": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "referrals": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "referrals/incoming": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "referrals/<pk>": {
        "doctor": ["PATCH"],
        "hospital_admin": ["PATCH"],
        "super_admin": ["PATCH"],
    },
    "consents": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "consents/list": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "consents/<pk>": {
        "doctor": ["PATCH"],
        "hospital_admin": ["PATCH"],
        "super_admin": ["PATCH"],
    },
    "break-glass": {
        "doctor": ["POST"],
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "break-glass/list": {
        "doctor": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "superadmin/onboarding-dashboard": {"super_admin": ["GET"]},
    "superadmin/hospitals/<pk>/bulk-import-staff": {"super_admin": ["POST"]},
    "superadmin/hospitals/<pk>/connectivity": {"super_admin": ["GET"]},
    "superadmin/cross-facility-activity": {"super_admin": ["GET"]},
    "superadmin/audit-chain-integrity": {"super_admin": ["GET"]},
    "superadmin/audit-chain-integrity/validate": {"super_admin": ["POST"]},
    "superadmin/hospital-onboarding": {"super_admin": ["GET"]},
    "superadmin/hospital-onboarding-list": {"super_admin": ["GET"]},
    "superadmin/compliance-alerts": {"super_admin": ["GET"]},
    "superadmin/pending-hospital-admin-assignments": {"super_admin": ["GET"]},
    "superadmin/pending-admin-grants": {"super_admin": ["GET"]},
    "lab/results/bulk-submit": {
        "lab_technician": ["POST"],
        "super_admin": ["POST"],
    },
    "lab/analytics/trends": {
        "lab_technician": ["GET"],
        "super_admin": ["GET"],
    },
    "nurse/shift/start": {"nurse": ["POST"], "super_admin": ["POST"]},
    "nurse/dashboard": {"nurse": ["GET"], "hospital_admin": ["GET"], "super_admin": ["GET"]},
    "nurse/worklist": {"nurse": ["GET"], "hospital_admin": ["GET"], "super_admin": ["GET"]},
    "nurse/shift/break-toggle": {"nurse": ["POST"], "super_admin": ["POST"]},
    "nurse/shift/end": {"nurse": ["POST"], "super_admin": ["POST"]},
    "nurse/shift/<pk>/handover": {"nurse": ["POST"], "super_admin": ["POST"]},
    "nurse/handover/<pk>/acknowledge": {"nurse": ["POST"], "super_admin": ["POST"]},
    "nurse/overdue-vitals": {
        "nurse": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "admin/users/<pk>/generate-reset-link": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/users/<pk>/generate-temp-password": {
        "hospital_admin": ["POST"],
        "super_admin": ["POST"],
    },
    "admin/password-resets": {
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "superadmin/users/<pk>/force-password-reset": {"super_admin": ["POST"]},
    "superadmin/users/<pk>/force-password-reset-initiate": {"super_admin": ["POST"]},
    "superadmin/password-resets/suspicious": {"super_admin": ["GET"]},
    "tasks": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "tasks/<pk>": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
    "tasks/<pk>/result": {
        "doctor": ["GET"],
        "nurse": ["GET"],
        "lab_technician": ["GET"],
        "receptionist": ["GET"],
        "pharmacist": ["GET"],
        "radiology_technician": ["GET"],
        "billing_staff": ["GET"],
        "ward_clerk": ["GET"],
        "hospital_admin": ["GET"],
        "super_admin": ["GET"],
    },
}


class PermissionValidator:
    """
    Validates requests against permission matrix.
    Provides centralized permission checking logic.
    """

    @staticmethod
    def get_endpoint_key(request_path: str) -> Optional[str]:
        """
        Convert request path to permission matrix key.
        Examples:
            /api/v1/patients/123 -> "patients/<pk>"
            /api/admin/users -> "admin/users"
        """
        # Remove /api/v1/ or /api/ prefix and query string (use removeprefix; lstrip would strip chars)
        path = request_path.split("?")[0]
        path = path.removeprefix("/api/v1/").removeprefix("/api/").lstrip("/")

        # Try exact match first
        if path in PERMISSION_MATRIX:
            return path

        # Try pattern matching for UUID paths
        import re
        path_parts = path.split("/")

        for matrix_key in PERMISSION_MATRIX.keys():
            matrix_parts = matrix_key.split("/")

            if len(path_parts) != len(matrix_parts):
                continue

            match = True
            for path_part, matrix_part in zip(path_parts, matrix_parts):
                if matrix_part in ("<pk>", "<uuid:pk>") and is_uuid(path_part):
                    continue
                if matrix_part in ("<id>", "<uuid:id>") and is_uuid(path_part):
                    continue
                if matrix_part.startswith("<") and matrix_part.endswith(">"):
                    # Generic parameter like <order_id>
                    continue
                if path_part != matrix_part:
                    match = False
                    break

            if match:
                return matrix_key

        return None

    @staticmethod
    def can_access(
        role: Optional[str],
        endpoint: str,
        method: str,
        require_hospital_scoping: bool = True,
    ) -> bool:
        """
        Check if user with given role can access endpoint with method.

        Args:
            role: User role (or None for public endpoints)
            endpoint: API endpoint key (e.g., "patients/<pk>")
            method: HTTP method (GET, POST, etc.)
            require_hospital_scoping: Whether endpoint requires hospital scoping

        Returns:
            True if access is allowed, False otherwise
        """
        if endpoint not in PERMISSION_MATRIX:
            return False

        allowed_roles = PERMISSION_MATRIX[endpoint]

        # Public endpoints
        if "public" in allowed_roles:
            return method in allowed_roles["public"]

        # Authenticated endpoints
        if "authenticated" in allowed_roles and role:
            return method in allowed_roles["authenticated"]

        # Role-specific endpoints
        if role in allowed_roles:
            return method in allowed_roles[role]

        return False

    @staticmethod
    def log_permission_denial(
        request,
        endpoint: str,
        reason: str,
        extra_data: dict = None,
    ):
        """Log permission denial for audit trail."""
        user = getattr(request, "user", None)
        hospital_id = getattr(request, "hospital_id", None)

        audit_data = {
            "event_type": "permission_denied",
            "endpoint": endpoint,
            "method": request.method,
            "reason": reason,
            "ip_address": get_client_ip(request),
        }

        if extra_data:
            audit_data.update(extra_data)

        logger.warning(
            f"Permission denied: {endpoint} {request.method} "
            f"user={user.id if user else 'anonymous'} reason={reason}"
        )

        # Log to database if user is authenticated
        if user and user.is_authenticated:
            try:
                ip = audit_data.get("ip_address") or get_client_ip(request)
                if ip == "unknown":
                    ip = "0.0.0.0"
                AuditLog.objects.create(
                    user=user,
                    action="permission_denied",
                    resource_type="endpoint",
                    resource_id=None,
                    hospital_id=hospital_id,
                    ip_address=ip,
                    extra_data=audit_data,
                )
            except Exception as e:
                logger.error(f"Failed to log permission denial: {e}")


def is_uuid(value: str) -> bool:
    """Check if value is a valid UUID."""
    import uuid
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def get_client_ip(request) -> str:
    """Get client IP from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


class RequiresRole(BasePermission):
    """
    DRF Permission class for role-based access control.

    Usage:
        @require_role("doctor", "super_admin")
        def my_view(request):
            ...
    """

    def __init__(self, *allowed_roles):
        self.allowed_roles = allowed_roles

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(request.user, "role", None)
        if role not in self.allowed_roles:
            return False

        return True


class PermissionEnforcementMiddleware:
    """
    Django middleware for centralized permission validation and logging.

    This middleware:
    1. Validates all API requests against permission matrix
    2. Logs permission denials to database
    3. Tracks metrics (success/failure by endpoint/role)
    4. Provides audit trail for compliance
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.validator = PermissionValidator()

    def __call__(self, request):
        # Only validate API requests
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Get endpoint key
        endpoint = self.validator.get_endpoint_key(request.path)

        # Check permissions
        user = request.user
        # DRF APIClient.force_authenticate() in tests may inject a forced user
        # before DRF authentication classes run; honor it for middleware checks.
        if (not user or not getattr(user, "is_authenticated", False)) and hasattr(request, "_force_auth_user"):
            forced_user = getattr(request, "_force_auth_user")
            if forced_user is not None:
                user = forced_user

        # IMPORTANT: This middleware runs before DRF view authentication.
        # If a Bearer token is present, authenticate it here so permission checks
        # use the real user role (otherwise request.user is anonymous).
        if not (user and getattr(user, "is_authenticated", False)):
            auth_header = request.META.get("HTTP_AUTHORIZATION", "") or ""
            if auth_header.lower().startswith("bearer "):
                try:
                    from rest_framework_simplejwt.authentication import JWTAuthentication
                    jwt_auth = JWTAuthentication()
                    auth_result = jwt_auth.authenticate(request)
                    if auth_result is not None:
                        user, _token = auth_result
                        request.user = user
                except Exception:
                    # If token is invalid/expired, let downstream auth handle 401;
                    # permission layer should not crash.
                    pass

        role = getattr(user, "role", None) if user and getattr(user, "is_authenticated", False) else None

        if endpoint:
            # If no authenticated user and endpoint is not public, return 401 (not 403).
            # This aligns with DRF/JWT semantics and avoids masking auth issues as RBAC issues.
            if not (user and getattr(user, "is_authenticated", False)):
                allowed_roles = PERMISSION_MATRIX.get(endpoint, {})
                if "public" not in allowed_roles or request.method not in allowed_roles.get("public", []):
                    return JsonResponse(
                        {"error": "authentication_required", "message": "Authentication required"},
                        status=401,
                    )

            # Dev-only bypass allowlist (DEBUG only)
            if getattr(settings, "DEBUG", False) and user and getattr(user, "is_authenticated", False):
                email = (getattr(user, "email", "") or "").strip().lower()
                if email and email in _dev_bypass_emails():
                    allowed = True
                else:
                    allowed = self.validator.can_access(role, endpoint, request.method)
            else:
                allowed = self.validator.can_access(role, endpoint, request.method)
            if not allowed:
                self.validator.log_permission_denial(
                    request,
                    endpoint,
                    f"Role '{role}' not allowed {request.method} {endpoint}",
                )
                return JsonResponse(
                    {
                        "error": "permission_denied",
                        "message": f"You do not have permission to access this endpoint",
                        "endpoint": endpoint,
                    },
                    status=403,
                )
        else:
            logger.warning(f"Unknown endpoint: {request.path}")
            if getattr(settings, "PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS", False):
                self.validator.log_permission_denial(
                    request,
                    request.path,
                    f"Unknown endpoint denied by fail-closed mode: {request.path}",
                    extra_data={"event_type": "unknown_endpoint_denied"},
                )
                return JsonResponse(
                    {
                        "error": "permission_denied",
                        "message": "Unknown API endpoint is blocked by permission policy",
                        "endpoint": request.path,
                    },
                    status=403,
                )

        # Continue to view
        response = self.get_response(request)
        return response


def require_role(*roles):
    """
    Decorator for role-based access control.

    Usage:
        @require_role("doctor", "super_admin")
        def my_view(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = request.user
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {"error": "authentication_required"},
                    status=401,
                )

            user_role = getattr(user, "role", None)
            if user_role not in roles:
                validator = PermissionValidator()
                validator.log_permission_denial(
                    request,
                    view_func.__name__,
                    f"Role '{user_role}' not in allowed roles {roles}",
                )
                return JsonResponse(
                    {"error": "permission_denied"},
                    status=403,
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


# Backward-compatible alias for integrations/tests that still reference PERMISSION_MAP.
PERMISSION_MAP = PERMISSION_MATRIX
