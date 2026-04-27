"""
T14: OpenAPI/Swagger Schema Generation Setup

This script sets up drf-spectacular for MedSync API documentation.

Installation:
  pip install drf-spectacular drf-spectacular-sidecar

Setup:
  1. Run: python manage.py spectacular --file docs/openapi.yaml
  2. Or view at: /api/schema/ (interactive Swagger UI)
  3. Or download: /api/schema.yaml (raw schema)

Usage:
  # Generate schema file
  python manage.py spectacular --file docs/openapi.yaml

  # Serve with Swagger UI (development)
  GET /api/schema/swagger-ui/
  GET /api/schema/redoc/
"""

# settings.py additions (to be merged into medsync_backend/settings.py):

SPECTACULAR_SETTINGS = {
    # Title and version
    "TITLE": "MedSync EMR API",
    "DESCRIPTION": """
    Centralized multi-hospital Electronic Medical Records (EMR) system.
    
    ## Authentication
    
    All endpoints except `/auth/login` and `/health` require JWT bearer token:
    
    ```
    Authorization: Bearer <access_token>
    ```
    
    Obtain token via:
    - `POST /auth/login` - Email + password login (TOTP if enabled)
    - `POST /auth/verify-otp` - Verify TOTP code
    - `POST /auth/refresh` - Refresh expired access_token
    
    ## Multi-Hospital Scoping
    
    - Non-super-admin users see only their hospital's data
    - Super admin can use `X-View-As-Hospital: <hospital_id>` header to view other hospitals
    - All data is hospital-scoped via `hospital_id` field
    
    ## Cross-Facility Access
    
    Access to other hospitals' data requires:
    1. **Consent** - Explicit permission granted by data-owning hospital
    2. **Referral** - Patient referred between hospitals
    3. **Break-Glass** - Emergency override (15-minute window, fully audited)
    
    ## Rate Limiting
    
    - Per user: 200 requests/hour
    - Per IP: 1000 requests/hour
    - Brute-force (login): 10 attempts/hour
    
    Returns `429 Too Many Requests` when limit exceeded.
    
    ## Audit Logging
    
    All mutations (CREATE, UPDATE, DELETE) and cross-facility access are logged
    in `AuditLog` with full context: user, timestamp, resource_id (sanitized),
    action, hospital, and details.
    
    ## API Versions
    
    - Current: v1 (at `/api/v1/`)
    - All endpoints are relative to `/api/v1/` unless noted
    """,
    "VERSION": "1.0.0",
    "CONTACT": {
        "name": "MedSync Support",
        "email": "support@medsync.health",
        "url": "https://medsync.health",
    },
    "LICENSE": {
        "name": "Proprietary",
        "url": "https://medsync.health/license",
    },
    
    # Schema generation
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_GENERATOR_CLASS": "drf_spectacular.generators.SchemaGenerator",
    
    # Server URLs
    "SERVERS": [
        {
            "url": "http://localhost:8000/api/v1",
            "description": "Development (local)",
        },
        {
            "url": "https://api-staging.railway.app/api/v1",
            "description": "Staging (Railway)",
        },
        {
            "url": "https://api.medsync.health/api/v1",
            "description": "Production",
        },
    ],
    
    # Security schemes
    "SECURITY": [
        {
            "Bearer Token": [],
        }
    ],
    "SECURITY_DEFINITIONS": {
        "Bearer Token": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token (15-minute TTL)",
        }
    },
    
    # Documentation customization
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "USE_SESSION_AUTH": False,  # We use JWT, not sessions
    
    # Spectacular extensions
    "TITLE_CASING": "title",
    "PREPROCESSING_HOOKS": [
        "drf_spectacular.hooks.build_mock_request",
    ],
    
    # Tag organization
    "TAGS": [
        {
            "name": "Authentication",
            "description": "Login, MFA, token refresh, logout, passkey enrollment",
        },
        {
            "name": "Patients",
            "description": "Patient registration, demographics, records retrieval",
        },
        {
            "name": "Encounters",
            "description": "Clinical visits (inpatient, outpatient, emergency)",
        },
        {
            "name": "Records",
            "description": "Diagnoses, prescriptions, vitals, nursing notes, lab orders",
        },
        {
            "name": "Appointments",
            "description": "Scheduling, check-in, rescheduling",
        },
        {
            "name": "Lab",
            "description": "Lab order management, results entry, verification",
        },
        {
            "name": "HIE (Health Information Exchange)",
            "description": "Consent, referrals, break-glass emergency access",
        },
        {
            "name": "Admin",
            "description": "Staff management, ward configuration, audit logs (super admin / hospital admin)",
        },
        {
            "name": "FHIR",
            "description": "FHIR-compliant read-only endpoints for interoperability",
        },
        {
            "name": "HL7",
            "description": "HL7 export and messaging endpoints",
        },
        {
            "name": "Health",
            "description": "System health and status (no authentication required)",
        },
    ],
}

# In settings.py INSTALLED_APPS, add:
# "drf_spectacular",

# In urls.py, add:
# from drf_spectacular.views import (
#     SpectacularAPIView,
#     SpectacularSwaggerView,
#     SpectacularRedocView,
# )
#
# urlpatterns = [
#     ...
#     path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
#     path("api/v1/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
#     path("api/v1/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
# ]
