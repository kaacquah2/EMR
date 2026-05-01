import os
from pathlib import Path
from decouple import config
import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 during build and at runtime. Settings are imported during `vercel build`
# before Neon/Secrets may be wired; relax only enough for that import and collectstatic.
_VERCEL = os.environ.get("VERCEL") == "1"

# Default False so production is safe if env is unset. Set DEBUG=True for local dev only.
DEBUG = config("DEBUG", default=False, cast=bool)

# SECRET_KEY: no insecure default when DEBUG=False. Accept SECRET_KEY or DJANGO_SECRET_KEY
# (os.environ first so Railway/Render-style names work; empty/whitespace counts as unset).


def _resolve_secret_key():
    for env_name in ("SECRET_KEY", "DJANGO_SECRET_KEY"):
        raw = os.environ.get(env_name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    cfg = config("SECRET_KEY", default=None)
    if cfg is not None and str(cfg).strip():
        return str(cfg).strip()
    return None


_SECRET_KEY = _resolve_secret_key()
if _SECRET_KEY is None:
    if DEBUG:
        # Local development: generate a temporary key (not for production)
        import secrets
        _SECRET_KEY = f"dev-{secrets.token_hex(32)}"
        import warnings
        warnings.warn(
            "⚠️  Using generated development SECRET_KEY. "
            "For production, set SECRET_KEY environment variable to a strong value.",
            RuntimeWarning,
            stacklevel=2,
        )
    elif _VERCEL:
        import warnings

        _SECRET_KEY = "vercel-bootstrap-insecure-set-secret-key-in-dashboard"
        warnings.warn(
            "SECRET_KEY unset on Vercel; using bootstrap placeholder. "
            "Set SECRET_KEY or DJANGO_SECRET_KEY in the Vercel project environment.",
            RuntimeWarning,
            stacklevel=2,
        )
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "SECRET_KEY is required when DEBUG=False. "
            "On Railway: Service → Variables → add SECRET_KEY (or DJANGO_SECRET_KEY) "
            "with a long random value (e.g. openssl rand -hex 32). Redeploy after saving."
        )
SECRET_KEY = _SECRET_KEY

_db_url_configured = bool(config("DATABASE_URL", default=""))
if DEBUG and _db_url_configured:
    import warnings
    warnings.warn(
        "DEBUG is True with DATABASE_URL set (local/staging only). Production must never run with DEBUG=True.",
        RuntimeWarning,
        stacklevel=2,
    )
# Production: never run with DEBUG=True. Set ENV=production (or use a dedicated flag) to enforce.
if config("ENV", default="").lower() == "production" and DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Production must not run with DEBUG=True. Set DEBUG=False.")

ALLOWED_HOSTS = [h.strip() for h in config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",") if h.strip()]
if _VERCEL:
    # Vercel deployment hostnames (*.vercel.app); override via ALLOWED_HOSTS if using a custom domain.
    ALLOWED_HOSTS = list({*ALLOWED_HOSTS, ".vercel.app"})
# Railway injects RAILWAY_PROJECT_ID (and often RAILWAY_PUBLIC_DOMAIN) on deploy. Without a matching
# host, requests to *.up.railway.app return HTTP 400 (DisallowedHost) before any view runs.
if os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    ALLOWED_HOSTS = list({*ALLOWED_HOSTS, ".up.railway.app"})
    _railway_pub = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
    if _railway_pub:
        ALLOWED_HOSTS = list({*ALLOWED_HOSTS, _railway_pub})

def _has_pkg(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False
_HAS_DAPHNE = _has_pkg("daphne")
_HAS_CHANNELS = _has_pkg("channels")

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
    "django_celery_beat",
    "django_celery_results",
    "core",
    "patients",
    "records",
    "interop",
    "shared.apps.SharedConfig",
    "api",
]
if _HAS_DAPHNE:
    INSTALLED_APPS.insert(0, "daphne")
if _HAS_CHANNELS:
    INSTALLED_APPS.insert(INSTALLED_APPS.index("rest_framework"), "channels")
if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS += ["debug_toolbar"]
    except ImportError:
        pass

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "shared.permissions.PermissionEnforcementMiddleware",
    "api.middleware.ForcedPasswordChangeMiddleware",
    "api.middleware.ViewAsHospitalMiddleware",
    "api.middleware.BreakGlassExpiryMiddleware",
    "api.middleware.anomaly_detection.AnomalyDetectionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.CSPMiddleware",
]
if DEBUG:
    try:
        import debug_toolbar
        MIDDLEWARE.insert(
            MIDDLEWARE.index("django.middleware.gzip.GZipMiddleware") + 1,
            "debug_toolbar.middleware.DebugToolbarMiddleware",
        )
    except ImportError:
        pass

ROOT_URLCONF = "medsync_backend.urls"
WSGI_APPLICATION = "medsync_backend.wsgi.application"
if _HAS_CHANNELS:
    ASGI_APPLICATION = "medsync_backend.asgi.application"
# Production: set REDIS_URL so real-time alerts (WebSocket) are broadcast across ASGI workers.
# InMemoryChannelLayer is single-process only; Redis is required for multi-worker deployments.
_redis_url = config("REDIS_URL", default="")
if _HAS_CHANNELS:
    if _redis_url:
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [_redis_url]},
            }
        }
    else:
        CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Database: Postgres (Neon) required for production (pgcrypto, RLS, concurrent writes).
# SQLite used only when DEBUG=True and DATABASE_URL is unset (local dev only).
_db_url = config("DATABASE_URL", default="")
if _db_url:
    _db_config = dj_database_url.parse(_db_url)
    if _db_config.get("ENGINE") == "django.db.backends.postgresql":
        _db_config.setdefault("OPTIONS", {})["sslmode"] = "require"
        _db_config["ENGINE"] = "api.db"
    _db_config.setdefault("CONN_MAX_AGE", 600)
    DATABASES = {"default": _db_config}
else:
    if not DEBUG:
        if _VERCEL:
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
                "DATABASE_URL is required in production. SQLite does not support pgcrypto, RLS, or safe concurrent writes. Use Neon (PostgreSQL) and set DATABASE_URL."
            )
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
# Database cache so MFA token survives runserver restarts (login -> mfa-verify). Run once: python manage.py createcachetable
# Vercel: no stable DB + no migrate for cache table — use in-memory cache (MFA may not survive cold starts).
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

# RBAC Fail-Closed Mode: Security-first API endpoint protection
# Default: False (fail-open) for safe development
# Production: Set to True ONLY after RBAC coverage is verified 100%
# See README.md section "RBAC Security: Fail-Closed Mode" for runbook
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS = config(
    "PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS",
    default=False,  # Changed from True to False for safety
    cast=bool,
)

# Log warnings if fail-closed is enabled but coverage may be incomplete
# This check validates at startup if enabled
_RBAC_COVERAGE_WARNING_ENABLED = (
    PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS and not DEBUG
)

def _validate_rbac_coverage_at_startup():
    """
    Validate RBAC coverage when fail-closed mode is enabled in production.
    Warns if coverage is < 100% (detected via test_rbac_coverage assertions).
    """
    if not _RBAC_COVERAGE_WARNING_ENABLED:
        return
    
    # Only run check in production (not DEBUG)
    # This prevents startup slowdown in development
    try:
        import logging
        logger = logging.getLogger("medsync.rbac")
        
        # Import and run the coverage test
        from api.tests.test_rbac_coverage import TestAllRoutesHavePermissions
        test = TestAllRoutesHavePermissions()
        test.test_every_url_has_permission_entry()
        
        logger.info("✅ RBAC coverage 100% validated - fail-closed mode active")
    except AssertionError as e:
        import logging
        logger = logging.getLogger("medsync.rbac")
        logger.error(
            f"⚠️  FAIL-CLOSED MODE ENABLED BUT COVERAGE < 100%\n"
            f"   Error: {e}\n"
            f"   New endpoints in api/urls.py are missing from shared/permissions.py\n"
            f"   These endpoints will return 403 Permission Denied until added to PERMISSION_MATRIX.\n"
            f"   To debug: Set PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=False and redeploy."
        )
        if not DEBUG:
            raise RuntimeError(
                "Production deployment blocked: RBAC coverage incomplete. "
                "See logs for details. Set PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=False to debug."
            )
    except Exception as e:
        # Fail safely: don't crash startup due to test infrastructure issues
        import logging
        logger = logging.getLogger("medsync.rbac")
        logger.warning(f"Could not validate RBAC coverage at startup: {e}")

# Run validation check if fail-closed mode enabled
if _RBAC_COVERAGE_WARNING_ENABLED:
    _validate_rbac_coverage_at_startup()

# Field-level encryption key for PHI columns (separate from DB encryption/TDE).
# In production, always set FIELD_ENCRYPTION_KEY from secrets manager.
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default=None)
if not FIELD_ENCRYPTION_KEY and not DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is required in production.")
CRYPTOGRAPHY_KEY = FIELD_ENCRYPTION_KEY

# Dev-only permission bypass (comma-separated emails). Guarded by DEBUG in middleware.
# Same list: MFA login uses TOTP/authenticator only (no email OTP)—those addresses are not real inboxes.
# All other users receive a one-time code by email after password login.
# Example:
# DEV_PERMISSION_BYPASS_EMAILS=admin@medsync.gh,doctor@medsync.gh,hospital_admin@medsync.gh,nurse@medsync.gh,receptionist@medsync.gh,lab_technician@medsync.gh,doctor2@medsync.gh
DEV_PERMISSION_BYPASS_EMAILS = [
    e.strip().lower()
    for e in config("DEV_PERMISSION_BYPASS_EMAILS", default="").split(",")
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
    "DEFAULT_THROTTLE_RATES": (
        {}
        if DEBUG
        else {
            "anon": THROTTLE_ANON,
            "user": THROTTLE_USER,
        }
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
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

# WebAuthn/Passkey Configuration
# WEBAUTHN_RP_ID: Your domain (e.g. "medsync.gh" in production, "localhost" for dev)
#   - Must NOT include protocol (http://, https://) or trailing slash
#   - Used as Relying Party ID in WebAuthn ceremonies
# WEBAUTHN_ORIGIN: Frontend origin (e.g. "https://medsync.gh" in production)
#   - Must be HTTPS in production (except localhost for dev)
#   - Must match browser's origin exactly (scheme://host:port)
# WEBAUTHN_ENABLED: Master switch to enable/disable passkey auth entirely
_WEBAUTHN_RP_ID = config("WEBAUTHN_RP_ID", default="localhost")
_WEBAUTHN_ORIGIN = config("WEBAUTHN_ORIGIN", default="http://localhost:3000")

# Validate WebAuthn configuration
def _validate_webauthn_config():
    """Validate WebAuthn RP ID and Origin configuration at startup."""
    import re
    
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

# AI/ML model paths (MEDIUM-4: environment-aware model locations)
# Default points at api/ai/models/*.joblib (written by api/ai/train_models.py).
_ai_models_dir = Path(
    config("MEDSYNC_AI_MODELS_DIR", default=str(BASE_DIR / "api" / "ai" / "models"))
).resolve()

MODEL_PATHS = {
    "risk_predictor": config(
        "MODEL_PATH_RISK_PREDICTOR",
        default=str(_ai_models_dir / "risk_predictor.joblib"),
    ),
    "diagnosis_classifier": config(
        "MODEL_PATH_DIAGNOSIS",
        default=str(_ai_models_dir / "diagnosis_classifier.joblib"),
    ),
    "triage_classifier": config(
        "MODEL_PATH_TRIAGE",
        default=str(_ai_models_dir / "triage_classifier.joblib"),
    ),
}

# AI/ML Clinical Features Deployment Gates
# PRODUCTION SAFETY: All clinical AI features are DISABLED by default until explicitly validated and approved
DISABLE_AI_CLINICAL_FEATURES = config("DISABLE_AI_CLINICAL_FEATURES", default=True, cast=bool)
AI_CLINICAL_FEATURES_ENABLED = config("AI_CLINICAL_FEATURES_ENABLED", default=False, cast=bool)
AI_CONFIDENCE_THRESHOLD_CLINICAL = config("AI_CONFIDENCE_THRESHOLD_CLINICAL", default=0.80, cast=float)
AI_CONFIDENCE_THRESHOLD_DEV = config("AI_CONFIDENCE_THRESHOLD_DEV", default=0.75, cast=float)

# Use clinical threshold in production, dev threshold otherwise
AI_CONFIDENCE_THRESHOLD = AI_CONFIDENCE_THRESHOLD_CLINICAL if not DEBUG else AI_CONFIDENCE_THRESHOLD_DEV

# Model training and validation tracking
# Phase 3 Complete: Using trained hybrid models (synthetic Ghana data + UCI readmission data)
# Can be overridden per hospital via admin approval workflow in AIDeploymentLog
AI_MODEL_VERSION = config("AI_MODEL_VERSION", default="1.0.0-hybrid")
AI_MODELS_TRAINED_ON_REAL_DATA = config("AI_MODELS_TRAINED_ON_REAL_DATA", default=True, cast=bool)

# Actual validation metrics from Phase 3 training run
# Source: Hybrid dataset (7,000 samples: 3,000 synthetic Ghana + 4,000 UCI readmission data)
# Training date: 2026-04-20
AI_MODELS_VALIDATION_METRICS = {
    'auc_roc': 0.5921,
    'sensitivity': 0.9013,
    'specificity': 0.2948,
    'data_source': 'hybrid',
    'training_date': '2026-04-20',
    'samples': 7000,
    'note': 'Development-grade models. Below clinical deployment thresholds (AUC≥0.80). '
            'Hospital admin can override approval for research/demo purposes with audit trail.',
}

_cors_default = (
    "https://configure-cors-in-vercel.invalid"
    if _VERCEL
    else "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in config(
    "CORS_ALLOWED_ORIGINS",
    default=_cors_default,
).split(",") if o.strip()]
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
    error_msg = "Production must set CORS_ALLOWED_ORIGINS to explicit HTTPS origins (e.g. https://app.example.com). "
    if _has_internal_origin:
        error_msg += "No internal network addresses (192.168.x.x, 10.0.x.x, etc.)."
    else:
        error_msg += "No wildcard (*) or HTTP origins."
    raise ImproperlyConfigured(error_msg)

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
_email_backend_requested = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="medsync@localhost")

# Push Notifications (Web Push / VAPID)
VAPID_PUBLIC_KEY = config('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = config('VAPID_PRIVATE_KEY', default='')
VAPID_CLAIM_EMAIL = config('VAPID_CLAIM_EMAIL', default='mailto:admin@medsync.gh')

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
    or config("ENV", default="").lower() == "production"
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
BREAK_GLASS_NOTIFY_EMAILS = [e.strip() for e in config("BREAK_GLASS_NOTIFY_EMAILS", default="").split(",") if e.strip()]
# Break-glass time window in minutes (15 minutes is the standard)
BREAK_GLASS_WINDOW_MINUTES = config("BREAK_GLASS_WINDOW_MINUTES", default=15, cast=int)

# No-show auto-marking settings
NO_SHOW_GRACE_PERIOD_MINUTES = config("NO_SHOW_GRACE_PERIOD_MINUTES", default=15, cast=int)
NO_SHOW_OVERRIDE_DAYS = config("NO_SHOW_OVERRIDE_DAYS", default=7, cast=int)

# Password Reset Security (CRITICAL FIX #2)
# Frontend URL for password reset page (must be HTTPS in production)
PASSWORD_RESET_FRONTEND_URL = config(
    "PASSWORD_RESET_FRONTEND_URL",
    default="https://medsync.example.com/auth/reset-password",
)
# Frontend base URL for activation and other frontend links
FRONTEND_URL = config(
    "FRONTEND_URL",
    default="https://medsync.example.com",
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
    _frontend_origin = config("FRONTEND_URL", default="https://medsync.example.com")
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
SESSION_COOKIE_SECURE = _SECURE_HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = _SECURE_HTTPS
CSRF_COOKIE_HTTPONLY = True  # FIXED: Now HttpOnly to prevent XSS cookie theft
CSRF_COOKIE_SAMESITE = "Strict"  # FIXED: Changed from Lax to Strict
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"  # Frontend sends CSRF token via X-CSRFToken header
CSRF_TRUSTED_ORIGINS = [o.strip() for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o.strip()]

# Django Debug Toolbar (DEBUG only): N+1 and query optimization
if DEBUG:
    INTERNAL_IPS = ["127.0.0.1", "::1"]

# ============================================================================
# CELERY CONFIGURATION (Async Task Queue)
# ============================================================================
_celery_broker_url = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
_celery_result_backend = config("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/0")

CELERY_BROKER_URL = _celery_broker_url
CELERY_RESULT_BACKEND = _celery_result_backend
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes hard limit
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Task-specific timeouts
CELERY_TASK_SOFT_TIME_LIMIT = 5 * 60  # 5 minutes soft limit (gives tasks time to cleanup)
CELERY_TASK_ACKS_LATE = True  # Acknowledge after task completion (prevents task loss)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Process one task at a time

# Retry policy for failed tasks
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_DEFAULT_RETRY_DELAY = 5  # Start with 5 seconds

# Celery Beat Schedule (Scheduled Tasks)
# Tasks run at specified intervals (e.g., no-show auto-marking every 15 minutes)
CELERY_BEAT_SCHEDULE = {
    'mark-no-shows-every-15-minutes': {
        'task': 'api.tasks.appointment_tasks.mark_no_shows_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'expires': 600}  # Expires in 10 minutes if not run
    }
}

# Celery Result Backend Configuration (for tracking task status)
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour

# ============================================================================
# DAPHNE ASGI SERVER CONFIGURATION (Development & Production)
# ============================================================================
# Daphne is the ASGI server for WebSocket support (Django Channels).
# In development, Daphne uses Django's autoreloader for hot-reload.
# This configuration ensures graceful shutdown during file reload.
# 
# Key settings:
# - application_close_timeout: Time to wait for app instance to shut down gracefully (seconds).
#   Default is 2; we increase to 5 to allow pending requests to complete before killing tasks.
# - ping_interval: WebSocket ping interval (seconds). Higher values reduce load.
# - ping_timeout: Time to wait for pong response before closing connection (seconds).
# 
# See: https://daphne.readthedocs.io/en/latest/
if DEBUG:
    # Development: longer timeout to allow requests to finish during reload
    DAPHNE_APPLICATION_CLOSE_TIMEOUT = 5
else:
    # Production: shorter timeout (hard kill after 2 seconds if not graceful)
    DAPHNE_APPLICATION_CLOSE_TIMEOUT = 2

# ============================================================================
# RBAC-18: Fail-closed mode for unknown API endpoints
# ============================================================================
# When True: any /api/* path NOT listed in PERMISSION_MATRIX returns 403.
# This prevents newly added endpoints from being publicly accessible before
# they are registered in the permission matrix.
#
# Development (DEBUG=True): False → allows rapid iteration without blocking
# Production (DEBUG=False): True → hard-fail for security
# ============================================================================
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS = not DEBUG
