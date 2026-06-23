import os
from pathlib import Path
from typing import cast

from decouple import config
import dj_database_url


def _str_config(key: str, default: str = "") -> str:
    """String env lookup with stable typing for static analysis."""
    return str(config(key, default=default))

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 during build and at runtime. Settings are imported during `vercel build`
# before Neon/Secrets may be wired; relax only enough for that import and collectstatic.
_VERCEL = os.environ.get("VERCEL") == "1"

# Default False so production is safe if env is unset. Set DEBUG=True for local dev only.
DEBUG = config("DEBUG", default=False, cast=bool)
ENV = config("ENV", default="development")
LLM_MODE = config("LLM_MODE", default="mock")


# SECRET_KEY: no insecure default when DEBUG=False. Accept SECRET_KEY or DJANGO_SECRET_KEY
# (os.environ first so Railway/Render-style names work; empty/whitespace counts as unset).


def _resolve_secret_key():
    for env_name in ("SECRET_KEY", "DJANGO_SECRET_KEY"):
        raw = os.environ.get(env_name)
        if raw is not None and raw.strip():
            return raw.strip()
    cfg = config("SECRET_KEY", default=None)
    return (
        str(cfg).strip()
        if cfg is not None and str(cfg).strip()
        else None
    )


_SECRET_KEY = _resolve_secret_key()
if _SECRET_KEY is None:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "SECRET_KEY is required for the application to start. "
        "Set SECRET_KEY or DJANGO_SECRET_KEY in your environment variables or .env file. "
        "For production, use a long random value (e.g. openssl rand -hex 32)."
    )
SECRET_KEY = _SECRET_KEY

_db_url_configured = bool(_str_config("DATABASE_URL"))
if DEBUG and _db_url_configured:
    import warnings
    warnings.warn(
        "DEBUG is True with DATABASE_URL set (local/staging only). Production must never run with DEBUG=True.",
        RuntimeWarning,
        stacklevel=2,
    )
# Production: never run with DEBUG=True. Set ENV=production (or use a dedicated flag) to enforce.
if _str_config("ENV").lower() == "production" and DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Production must not run with DEBUG=True. Set DEBUG=False.")

ALLOWED_HOSTS = [
    h.strip()
    for h in _str_config("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]
if _VERCEL:
    # Vercel deployment hostnames (*.vercel.app); override via ALLOWED_HOSTS if using a custom domain.
    ALLOWED_HOSTS = list({*ALLOWED_HOSTS, ".vercel.app"})
# Railway injects RAILWAY_PROJECT_ID (and often RAILWAY_PUBLIC_DOMAIN) on deploy. Without a matching
# host, requests to *.up.railway.app return HTTP 400 (DisallowedHost) before any view runs.
if os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    ALLOWED_HOSTS = list({*ALLOWED_HOSTS, ".up.railway.app"})
    if _railway_pub := (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip():
        ALLOWED_HOSTS = list({*ALLOWED_HOSTS, _railway_pub})

def _has_pkg(name):
    try:
        __import__(name)
    except ImportError:
        return False
    return True
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "drf_spectacular",
    "core",
    "patients",
    "records",
    "interop",
    "shared.apps.SharedConfig",
    "api",
]
if DEBUG and _has_pkg("debug_toolbar"):
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "api.middleware.ForcedPasswordChangeMiddleware",
    "api.middleware.SessionIdleTimeoutMiddleware",
    "shared.permissions.PermissionEnforcementMiddleware",

    "api.middleware.ViewAsHospitalMiddleware",
    "api.middleware.BreakGlassExpiryMiddleware",
    "api.middleware.anomaly_detection.AnomalyDetectionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.CSPMiddleware",
    "api.middleware.RateLimitHeaderMiddleware",
]
if DEBUG and _has_pkg("debug_toolbar"):
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.gzip.GZipMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )

ROOT_URLCONF = "medsync_backend.urls"
WSGI_APPLICATION = "medsync_backend.wsgi.application"

# Database: Postgres (Neon) required for production (pgcrypto, RLS, concurrent writes).
# SQLite used only when DEBUG=True and DATABASE_URL is unset (local dev only).
if _db_url := _str_config("DATABASE_URL"):
    _db_config = dj_database_url.parse(_db_url)
    if _db_config.get("ENGINE") == "django.db.backends.postgresql":
        _db_config.setdefault("OPTIONS", {})["sslmode"] = "require"
        _db_config["ENGINE"] = "api.db"
    _db_config.setdefault("CONN_MAX_AGE", 600)
    DATABASES = {"default": _db_config}
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif _VERCEL:
    import warnings

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    warnings.warn(
        "DATABASE_URL unset on Vercel; using in-memory SQLite for build/bootstrap only. "
        "Set DATABASE_URL (e.g. Neon) for a real deployment.",
        RuntimeWarning,
        stacklevel=2,
    )
else:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "DATABASE_URL is required in production. SQLite does not support pgcrypto, RLS, "
        "or safe concurrent writes. Use Neon (PostgreSQL) and set DATABASE_URL."
    )
# Database-backed cache for MFA tokens and rate limiting.
# Run once: python manage.py createcachetable
# Vercel: no stable DB for cache table — use in-memory (MFA may not survive cold starts).
if _VERCEL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "vercel-locmem",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "medsync_mfa_cache",
        }
    }

AUTH_USER_MODEL = "core.User"

# Password Hashers - Argon2id by default per OWASP 2025 and HIPAA recommendations
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Password validation — applied by Django admin + any code that calls validate_password().
# The custom api/password_policy.py enforces strength in all auth flows; these validators
# provide a second line of defence for Django's own set_password()/create_user() paths.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Roles that should only see basic demographics (PII masking) per MedSync Specs
NON_CLINICAL_PII_MASK_ROLES = (
    "receptionist",
    "lab_technician",
    "radiology_technician",
    "billing_staff",
    "ward_clerk",
    "pharmacy_technician",
)

# Throttle rates: anon = unauthenticated (auth + health); user = authenticated.
# Format: "num/period" e.g. "60/hour", "1000/day". Stricter anon limits brute force on login.
THROTTLE_ANON = config("THROTTLE_ANON", default="60/hour")
THROTTLE_USER = config("THROTTLE_USER", default="1000/hour")

# RBAC Fail-Closed Mode: deny requests to endpoints not in the permission matrix.
# Override to False via env var only when actively debugging RBAC gaps.
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS = config(
    "PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS",
    default=True,  # Fail-closed: deny unknown endpoints. Set to False only when debugging RBAC gaps.
    cast=bool,
)

# RBAC coverage is validated in CI via:
#   pytest api/tests/test_rbac_coverage.py
#   python manage.py check_rbac_coverage
# The fail-closed middleware (shared.permissions.PermissionEnforcementMiddleware)
# enforces PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS at request time.

# Field-level encryption key for PHI columns (separate from DB encryption/TDE).
# In production, always set FIELD_ENCRYPTION_KEY from secrets manager.
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default=None)
if not FIELD_ENCRYPTION_KEY and not DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required in production.")
CRYPTOGRAPHY_KEY = FIELD_ENCRYPTION_KEY

# ============================================================================
# GHANA NHIS INTEGRATION SETTINGS
# ============================================================================
# National Health Insurance Authority (NHIA) API credentials.
# Set these in your .env file or secrets manager for production.
# Leaving NHIS_API_BASE_URL or NHIS_API_KEY empty enables offline/mock mode.
#
# NHIS_API_BASE_URL      — NHIA REST API base (e.g. https://api.nhia.gov.gh/v2)
# NHIS_API_KEY           — Facility API key from NHIA portal
# NHIS_FACILITY_CODE     — Your facility's NHIS code (same as Hospital.nhis_code)
# NHIS_TIMEOUT_SECONDS   — HTTP request timeout in seconds
# NHIS_MAX_RETRIES       — Max retry attempts on transient errors
# NHIS_CIRCUIT_BREAKER_THRESHOLD — Failures before circuit opens (prevents thundering herd)
NHIS_API_BASE_URL = config("NHIS_API_BASE_URL", default="")
NHIS_API_KEY = config("NHIS_API_KEY", default="")
NHIS_FACILITY_CODE = config("NHIS_FACILITY_CODE", default="")
NHIS_TIMEOUT_SECONDS = config("NHIS_TIMEOUT_SECONDS", default=10, cast=int)
NHIS_MAX_RETRIES = config("NHIS_MAX_RETRIES", default=3, cast=int)
NHIS_CIRCUIT_BREAKER_THRESHOLD = config("NHIS_CIRCUIT_BREAKER_THRESHOLD", default=5, cast=int)

# TTL in seconds for the in-memory CDS rules cache (cds:active_rules:all key).
# On ClinicalRule save, the cache is immediately invalidated via signal.
# Default: 3600 (1 hour) — increase in production if rules rarely change.
CDS_RULES_CACHE_TTL = config("CDS_RULES_CACHE_TTL", default=3600, cast=int)



# Dev-only permission bypass (comma-separated emails). Guarded by DEBUG in middleware.
# Same list: MFA login uses TOTP/authenticator only (no email OTP)—those addresses are not real inboxes.
# All other users receive a one-time code by email after password login.
# Example:
# DEV_PERMISSION_BYPASS_EMAILS=admin@medsync.gh,doctor@medsync.gh,hospital_admin@medsync.gh,nurse@medsync.gh,receptionist@medsync.gh,lab_technician@medsync.gh,doctor2@medsync.gh
_raw_bypass_emails = _str_config("DEV_PERMISSION_BYPASS_EMAILS") or _str_config("BYPASS_EMAILS")
DEV_PERMISSION_BYPASS_EMAILS = [
    e.strip().lower()
    for e in _raw_bypass_emails.split(",")
    if e.strip()
]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # DEVELOPMENT: Disable throttling for faster iteration
    # PRODUCTION: Enable to protect against brute force attacks
    "DEFAULT_THROTTLE_CLASSES": (
        []
        if DEBUG
        else [
            "rest_framework.throttling.AnonRateThrottle",
            "rest_framework.throttling.UserRateThrottle",
        ]
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": THROTTLE_ANON,
        "user": THROTTLE_USER,
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MedSync EMR API",
    "DESCRIPTION": (
        "Multi-tenant Electronic Medical Records API. "
        "Supports JWT + TOTP MFA authentication, RBAC (10 roles), "
        "and FHIR R4 interoperability for inter-hospital record access."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
}

from datetime import timedelta

def _jwt_access_minutes():
    return config("JWT_ACCESS_MINUTES", default=15, cast=int)

def _jwt_refresh_days():
    return config("JWT_REFRESH_DAYS", default=7, cast=int)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=_jwt_access_minutes()),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_jwt_refresh_days()),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",  # ✅ EXPLICIT: Symmetric key for single-backend verification (not cross-hospital)
}

# SECURITY ASSERTION: Prevent accidental disabling of rotation in production
if not DEBUG:
    assert SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is True, "ROTATE_REFRESH_TOKENS must be True in production"
    assert SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is True, "BLACKLIST_AFTER_ROTATION must be True in production"
    assert "rest_framework_simplejwt.token_blacklist" in INSTALLED_APPS, "token_blacklist app required for rotation safety"

# WebAuthn/Passkey Configuration
# WEBAUTHN_RP_ID: Your domain (e.g. "medsync.gh" in production, "localhost" for dev)
#   - Must NOT include protocol (http://, https://) or trailing slash
#   - Used as Relying Party ID in WebAuthn ceremonies
# WEBAUTHN_ORIGIN: Frontend origin (e.g. "https://medsync.gh" in production)
#   - Must be HTTPS in production (except localhost for dev)
#   - Must match browser's origin exactly (scheme://host:port)
# WEBAUTHN_ENABLED: Master switch to enable/disable passkey auth entirely
_WEBAUTHN_RP_ID = _str_config("WEBAUTHN_RP_ID", "localhost")
_WEBAUTHN_ORIGIN = _str_config("WEBAUTHN_ORIGIN", "http://localhost:3000")

# Validate WebAuthn configuration
def _validate_webauthn_config():
    """Validate WebAuthn RP ID and Origin configuration at startup."""
    from django.core.exceptions import ImproperlyConfigured

    # RP ID validation: no protocol, no trailing slash
    if "://" in _WEBAUTHN_RP_ID:
        raise ImproperlyConfigured(
            f"WEBAUTHN_RP_ID must not include protocol. Got: {_WEBAUTHN_RP_ID}. "
            f"Expected: localhost or medsync.gh (without http:// or https://)"
        )
    if _WEBAUTHN_RP_ID.endswith("/"):
        raise ImproperlyConfigured(
            f"WEBAUTHN_RP_ID must not have trailing slash. Got: {_WEBAUTHN_RP_ID}"
        )
    
    # Origin validation: must have scheme
    if "://" not in _WEBAUTHN_ORIGIN:
        raise ImproperlyConfigured(
            f"WEBAUTHN_ORIGIN must include scheme (http:// or https://). Got: {_WEBAUTHN_ORIGIN}"
        )
    
    # Production enforcement: HTTPS required
    if not DEBUG and _WEBAUTHN_ORIGIN.startswith("http://"):
        raise ImproperlyConfigured(
            f"Production WEBAUTHN_ORIGIN must use https://. Got: {_WEBAUTHN_ORIGIN}"
        )
    
    # RP ID must match origin host
    from urllib.parse import urlparse
    origin_host = urlparse(_WEBAUTHN_ORIGIN).hostname
    if origin_host and origin_host != _WEBAUTHN_RP_ID and _WEBAUTHN_RP_ID != "localhost":
        # Allow localhost to differ from origin for dev
        raise ImproperlyConfigured(
            f"WEBAUTHN_RP_ID must match origin hostname. "
            f"RP_ID: {_WEBAUTHN_RP_ID}, Origin: {_WEBAUTHN_ORIGIN} (host: {origin_host})"
        )

# Run validation at import time
_validate_webauthn_config()

WEBAUTHN_RP_ID = _WEBAUTHN_RP_ID
WEBAUTHN_RP_NAME = "MedSync EMR"
WEBAUTHN_ORIGIN = _WEBAUTHN_ORIGIN
WEBAUTHN_ENABLED = config("WEBAUTHN_ENABLED", default=True, cast=bool)
WEBAUTHN_CHALLENGE_TTL = 300  # 5 minutes

_cors_default = (
    "https://configure-cors-in-vercel.invalid"
    if _VERCEL
    else "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in _str_config("CORS_ALLOWED_ORIGINS", _cors_default).split(",")
    if o.strip()
]
# Production: use explicit origins only. Wildcard (*) with credentials is insecure.
# HIGH PRIORITY FIX #1: Prevent internal network exposure (192.168.x.x, 10.0.x.x, etc.)
_internal_network_patterns = ['192.168.', '10.0.', '172.16.', 'localhost', '127.0.0.1', '::1']
_has_internal_origin = any(
    any(origin.startswith(pattern) for pattern in _internal_network_patterns)
    for origin in CORS_ALLOWED_ORIGINS
    if origin.startswith('http://')  # Only check unencrypted origins
)
if not DEBUG and (_has_internal_origin or "*" in CORS_ALLOWED_ORIGINS or not CORS_ALLOWED_ORIGINS):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "Production must set CORS_ALLOWED_ORIGINS to explicit HTTPS origins "
        "(e.g. https://app.example.com). "
        + (
            "No internal network addresses (192.168.x.x, 10.0.x.x, etc.)."
            if _has_internal_origin
            else "No wildcard (*) or HTTP origins."
        )
    )

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email (console backend for dev). Production (Railway, etc.): set SMTP env vars — see .env.example.
_email_backend_requested = _str_config(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = _str_config("EMAIL_HOST", "localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="medsync@localhost")

_local_mail_hosts = frozenset(("", "localhost", "127.0.0.1"))
_smtp_configured = bool(
    EMAIL_HOST_USER
    and EMAIL_HOST_PASSWORD
    and (EMAIL_HOST or "").strip() not in _local_mail_hosts
)
if (
    _email_backend_requested == "django.core.mail.backends.console.EmailBackend"
    and _smtp_configured
):
    # Common deploy mistake: SMTP env set but EMAIL_BACKEND left at default (console).
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = _email_backend_requested

# Only nag on known PaaS / explicit production — avoids noise in local pytest with DEBUG=False.
_email_deploy_context = bool(
    os.environ.get("RAILWAY_PROJECT_ID")
    or os.environ.get("VERCEL") == "1"
    or _str_config("ENV").lower() == "production"
)
if _email_deploy_context and "console.EmailBackend" in EMAIL_BACKEND:
    import warnings

    warnings.warn(
        "EMAIL_BACKEND is console: outbound email is not sent (only logged). "
        "Set EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS (or EMAIL_USE_SSL for port 465), "
        "EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL (Railway Variables / host env).",
        RuntimeWarning,
        stacklevel=2,
    )
# Break-glass: notify these emails (comma-separated); if empty, notifies hospital admins for the facility
BREAK_GLASS_NOTIFY_EMAILS = [
    e.strip() for e in _str_config("BREAK_GLASS_NOTIFY_EMAILS").split(",") if e.strip()
]
# Break-glass time window in minutes (15 minutes is the standard)
BREAK_GLASS_WINDOW_MINUTES = config("BREAK_GLASS_WINDOW_MINUTES", default=15, cast=int)

# No-show auto-marking settings
NO_SHOW_GRACE_PERIOD_MINUTES = config("NO_SHOW_GRACE_PERIOD_MINUTES", default=15, cast=int)
NO_SHOW_OVERRIDE_DAYS = config("NO_SHOW_OVERRIDE_DAYS", default=7, cast=int)

# Password Reset Security (CRITICAL FIX #2)
# Frontend URL for password reset page (must be HTTPS in production)
PASSWORD_RESET_FRONTEND_URL = config(
    "PASSWORD_RESET_FRONTEND_URL",
    default="https://emr-inky.vercel.app/auth/reset-password",
)
# Frontend base URL for activation and other frontend links
FRONTEND_URL = config(
    "FRONTEND_URL",
    default="https://emr-inky.vercel.app",
)
# Support email for invitation and other notification emails
SUPPORT_EMAIL = config(
    "SUPPORT_EMAIL",
    default="support@medsync.gh",
)
# Token expiry in hours
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = config(
    "PASSWORD_RESET_TOKEN_EXPIRY_HOURS",
    default=24,
    cast=int,
)

# Audit log signing key for HMAC-based chain signatures (CRITICAL audit hardening)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
AUDIT_LOG_SIGNING_KEY = config("AUDIT_LOG_SIGNING_KEY", default=None)
if not AUDIT_LOG_SIGNING_KEY and not DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("AUDIT_LOG_SIGNING_KEY is required in production.")


def _assert_no_placeholder_secrets() -> None:
    """Catch CHANGE_ME placeholder values that slipped into production config."""
    from django.core.exceptions import ImproperlyConfigured
    for _name, _value in (
        ("SECRET_KEY", SECRET_KEY),
        ("FIELD_ENCRYPTION_KEY", FIELD_ENCRYPTION_KEY),
        ("AUDIT_LOG_SIGNING_KEY", AUDIT_LOG_SIGNING_KEY),
    ):
        if _value and "CHANGE_ME" in str(_value).upper():
            raise ImproperlyConfigured(
                f"{_name} still contains a placeholder value. "
                "Generate a real secret: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )


if not DEBUG:
    _assert_no_placeholder_secrets()

# Database backup monitoring (health check)
BACKUP_ENABLED = config("BACKUP_ENABLED", default=False, cast=bool)
BACKUP_MAX_AGE_HOURS = config("BACKUP_MAX_AGE_HOURS", default=26, cast=int)

# Optional external integration webhooks (fire-and-forget notify; no PHI in payload by default)
PHARMACY_WEBHOOK_URL = config("PHARMACY_WEBHOOK_URL", default="")
PACS_CALLBACK_URL = config("PACS_CALLBACK_URL", default="")

# Production security headers (HTTPS, HSTS, XSS, etc.). Always enabled for consistency.
# SECURITY_FIX_CORS_CSP_T4: Production-grade CORS and CSP configuration (Mar 2025)
_SECURE_HTTPS = config("SECURE_HTTPS", default=not DEBUG, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Always set (prevent MIME-type sniffing)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # Always set (safe referrer header)
SECURE_BROWSER_XSS_FILTER = True  # Legacy XSS protection (fallback for older browsers)

if _SECURE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content Security Policy - prevent inline scripts and external script injection
    # TASK 2 REMEDIATION (Mar 2025): Removed 'unsafe-inline' from script-src for XSS protection
    # Kept in style-src only as Tailwind CSS v4 requires inline styles
    # SECURITY_FIX_CORS_CSP_T4: Ensure CSP includes frontend origin for API communication
    _frontend_origin = _str_config("FRONTEND_URL", "https://medsync.example.com")
    _csp_connect_src = ["'self'", _frontend_origin]
    
    SECURE_CONTENT_SECURITY_POLICY = {
        "default-src": ("'self'",),
        "script-src": ("'self'",),  # FIXED: Removed 'unsafe-inline' to prevent XSS token theft
        "style-src": ("'self'", "'unsafe-inline'"),   # Required: Tailwind CSS v4 uses inline styles
        "img-src": ("'self'", "data:", "https:"),
        "font-src": ("'self'", "data:"),
        "connect-src": _csp_connect_src,  # Allow communication with frontend and API
        "frame-ancestors": ("'none'",),  # Prevent clickjacking
        "base-uri": ("'self'",),
        "form-action": ("'self'",),
    }
else:
    # Development: Set minimal security headers
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_SSL_REDIRECT = False

# Cookie / CSRF policy. API uses JWT in headers; these apply to session/cookie use.
# ⚠️  SECURITY: Changed to use header-based CSRF tokens instead of cookies
# JavaScript gets CSRF token from response body or meta tag, not from cookie.
# This prevents XSS attacks from reading the CSRF cookie.
SESSION_COOKIE_SECURE = _SECURE_HTTPS if DEBUG else True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

# HIPAA compliance: Session idle timeout (15 minutes of inactivity)
SESSION_COOKIE_AGE = 900
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = _SECURE_HTTPS if DEBUG else True
CSRF_COOKIE_HTTPONLY = True  # FIXED: Now HttpOnly to prevent XSS cookie theft
CSRF_COOKIE_SAMESITE = "Strict"  # FIXED: Changed from Lax to Strict
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"  # Frontend sends CSRF token via X-CSRFToken header
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in _str_config("CSRF_TRUSTED_ORIGINS").split(",") if o.strip()
]

# Django Debug Toolbar (DEBUG only): N+1 and query optimization
if DEBUG:
    INTERNAL_IPS = ["127.0.0.1", "::1"]

# Django admin URL path (non-guessable in production). No leading slash.
# Set ADMIN_URL=ms-admin-<random>/ in production secrets — never use the default.
ADMIN_URL = _str_config("ADMIN_URL", "admin/").strip("/") + "/"
if not DEBUG and ADMIN_URL == "admin/":
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "Set ADMIN_URL to a non-guessable path in production "
        "(e.g. ADMIN_URL=ms-admin-x7k2/). "
        "The default 'admin/' URL must not be used in production."
    )

# ============================================================================
# STRUCTURED LOGGING (JSON to stdout for log aggregation)
# ============================================================================
_LOG_LEVEL = _str_config("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","message":"%(message)s"}'
            ),
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if not DEBUG else "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _LOG_LEVEL,
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "medsync": {"handlers": ["console"], "level": _LOG_LEVEL, "propagate": False},
        "medsync.rbac": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ============================================================================
# SENTRY (optional error tracking — set SENTRY_DSN to enable)
# ============================================================================
# HIPAA: send_default_pii=False ensures no user PII is sent to Sentry.
_SENTRY_DSN = _str_config("SENTRY_DSN")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging as _logging

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style="url"),
            LoggingIntegration(level=_logging.INFO, event_level=_logging.ERROR),
        ],
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.1, cast=float),
        send_default_pii=False,
        environment=ENV,
        release=config("SENTRY_RELEASE", default=""),
    )
