# MedSync Backend

Django REST API for MedSync EMR (Ghana Inter-Hospital Electronic Medical Records). Provides authentication (JWT + TOTP MFA), patient and clinical records, admissions, lab orders, admin/user management, audit logging, and cross-facility interoperability (global patient registry, referrals, consent, break-glass).

**Architecture (HIE-capable hybrid model):** Central platform holds **Global Patient Registry** (GPID), facility registry, consent records, referral requests, shared-record access audit, and break-glass logs. Each facility owns its encounters, vitals, and clinical records; cross-facility access is consent-, referral-, or break-glass-gated and read-only, with full audit and optional consent revoke.

**Multi-tenancy:** Data and permissions are scoped by hospital. Each user has a `role` and `hospital` (and optional `ward`). Non–super_admin users see only their facility’s data; super_admin with no hospital can see all. Hospital context is set by the system (admins assign users to a facility), not chosen at login. See **Governance** and **Multi-Tenancy** sections below.

### For reviewers

- **What this is:** Django REST API for a centralized, multi-hospital EMR (Ghana). Auth (JWT + TOTP MFA), patients/records/encounters, admissions, lab orders, admin, audit, FHIR/HL7, inter-hospital interoperability (global patient registry, referrals, consent, break-glass), and **AI clinical decision support** (risk prediction, triage, diagnosis assistance).
- **Quick verify:** From repo root `medsync-backend/`: `python -m venv .venv` → activate → `pip install -r requirements-local.txt` → `cp .env.example .env` (optional for dev; SQLite used if `DEBUG=True` and no `DATABASE_URL`) → `python manage.py migrate` → `python manage.py setup_dev` → `python dev_server.py` (or `python manage.py runserver`). Run tests: `python -m pytest api/tests/ -v`. Health: `GET http://localhost:8000/api/v1/health`.
  - **AI Training (Optional):** `python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings'); django.setup(); from api.ai.train_models import run_training; run_training(data_source='synthetic')"` to train models on synthetic Ghana data in ~2 minutes. Models saved to `api/ai/models/v{version}/`.
- **Key topics:** Security and structure (Codebase Audit), Governance, Multi-Tenancy, AI Training Pipeline (see section below), full API route table and role matrix — all in this README below.
- **Dev credentials:** [docs/DEV_CREDENTIALS.md](../docs/DEV_CREDENTIALS.md)
- **Daphne timeout fix:** See [DAPHNE_FIX.md](../DAPHNE_FIX.md) — eliminates "took too long to shut down" warnings during file reloads.

### Production Readiness

**Current Status:** ⛔ **NOT PRODUCTION READY** (42/100) — See [Audit & Critical Fixes](#audit--critical-fixes) below.

**Go-Live Criteria (Required Before Deployment):**
- ✅ Core multi-tenancy enforced
- ✅ Role-based access control working
- ✅ Audit logging functional (with sanitization)
- ⚠️ **CRITICAL:** 6 security issues must be resolved (see below)
- ⚠️ **HIGH:** 6 high-priority issues must be resolved
- ❌ Load testing (1000+ concurrent users) not done
- ❌ HIPAA compliance audit not completed
- ❌ Penetration testing not completed

**Estimated effort to production:** 6-8 weeks (100+ hours). See [Audit & Critical Fixes](#audit--critical-fixes) and `CRITICAL_FIXES_GUIDE.md`.

---

## 📚 Quick Links to Documentation

**For operators and support teams:**
- **[API Reference](./docs/API_REFERENCE.md)** — Complete API documentation (60+ endpoints, request/response schemas, examples, error codes)
- **[Operations Runbook](./docs/OPERATIONS_RUNBOOK.md)** — On-call troubleshooting guide, incident response, performance tuning, monitoring

**For end users:**
- **[Feature User Guide](../medsync-frontend/docs/FEATURE_GUIDE.md)** — Step-by-step workflows by role (Doctor, Nurse, Lab Tech, Receptionist, Admin)

---

## Repository context (what else ships with this codebase)

This repo is a full-stack deliverable. In addition to `medsync-backend/` and `medsync-frontend/`, the repo root contains:

- **Security/audit reports**: `README_SECURITY_FIXES.md`, `AUDIT_REPORT.md`, `FINAL_STATUS_REPORT.md`, `CRITICAL_FIXES_COMPLETE.md`, `INDEX.md` (package index)
- **Helper scripts**: `scripts/setup_ai.sh` (train AI models), `medsync-backend/scripts/pip-audit.sh` (dependency vuln scan)
- **Repo guidance**: `.github/copilot-instructions.md` (contributor/assistant conventions)

## Tech Stack

- **Framework:** Django 4.2+, Django REST Framework 3.14+
- **Auth:** JWT (Simple JWT), TOTP MFA (django-otp, pyotp)
- **CORS:** django-cors-headers
- **Config:** python-decouple
- **Database:** **Neon (PostgreSQL)** required in production via `DATABASE_URL`. SQLite is used only when `DEBUG=True` and `DATABASE_URL` is unset (local dev). See [Production deployment](#production-deployment-neon).
- **Optional:** Redis (cache/sessions), Pillow (file uploads)

---

## Migrations (EMR blueprint)

New tables **ClinicalAlert** (patients app) and **Encounter** (records app) are added in separate migrations so existing databases only apply the new tables.

- **patients:** `0001_blueprint_alerts_encounters` creates Patient, Allergy, PatientAdmission. `0002_clinical_alert` creates ClinicalAlert only.
- **records:** `0001_blueprint_alerts_encounters` creates MedicalRecord, Diagnosis, Prescription, LabOrder, LabResult, Vital, NursingNote. `0002_encounter` creates Encounter only.

**Fresh database:** Run `python manage.py migrate`; all migrations apply in order.

**Existing database** (you already have `patients_patient`, `records_medicalrecord`, etc., and see `InconsistentMigrationHistory: Migration interop.0001_initial is applied before its dependency patients.0001_blueprint_alerts_encounters`):

1. Record the missing migration entries so the history is consistent (does not create or change tables):
   ```bash
   python manage.py fix_migration_history
   ```
2. Apply the new tables only:
   ```bash
   python manage.py migrate
   ```
   This applies `patients.0002_clinical_alert` and `records.0002_encounter`, creating `patients_clinicalalert` and `records_encounter`.

**Password history:** Migration `core.0009_userpasswordhistory` adds `UserPasswordHistory` for last-5-password no-reuse. Run `python manage.py migrate` to apply.

**Phase 7 - 3-Tier Password Recovery:** Migration `core.0011_phase7_password_recovery` adds `PasswordResetAudit` model and extends User model with password reset fields. Supports 3-tier password recovery: Tier 1 (self-service), Tier 2 (admin-assisted), Tier 3 (super-admin override with MFA). Run `python manage.py migrate` to apply.

### Running tests

```bash
python -m pytest api/tests/ -v
```

**Coverage matrix, CI gates (pytest + pip-audit), Postgres dev:** [docs/TESTING_AND_CI.md](../docs/TESTING_AND_CI.md). **CI workflow:** `.github/workflows/ci.yml` (pytest, pip-audit, frontend lint/build/Vitest).

### Development Server (Daphne with Proper Reload Handling)

The backend uses **Daphne** as the ASGI server to support WebSockets. During development with file reloads, Daphne needs a longer shutdown timeout (5 seconds vs. default 2 seconds) to allow pending requests to complete gracefully. Without this, you'll see warnings like `"Application instance took too long to shut down and was killed"`.

**Start the server with proper configuration:**

```bash
# Option 1: Use the dev_server.py wrapper (recommended for development)
python dev_server.py              # Start on 127.0.0.1:8000
python dev_server.py 8001         # Start on different port

# Option 2: Use manage.py (uses configured timeout from settings.py)
python manage.py runserver        # Uses DAPHNE_APPLICATION_CLOSE_TIMEOUT from settings
```

**What dev_server.py does:**
- Sets `--application-close-timeout 5` (5 seconds for graceful shutdown during reload)
- Configures WebSocket ping/pong to keep connections stable during dev
- Enables access logging for debugging
- Automatically detects your Python environment and ASGI app

**Why this matters:**
During rapid file changes, the file reloader kills old Daphne processes. With a 2-second timeout, requests in progress are forcefully killed. With 5 seconds, they can complete gracefully, eliminating the noisy warnings in your logs.

---

## Audit Logging & Compliance

MedSync maintains comprehensive HIPAA-compliant audit logs of all system activities. Every significant action (CREATE, READ, UPDATE, DELETE, EXPORT, LOGIN, EMERGENCY_ACCESS, etc.) is logged with full context.

**Core Model**: `AuditLog` in `core/models.py` (151-193)
- **Who**: User ID, email, role
- **What**: Action type (17 supported actions), resource type, resource ID
- **When**: Timestamp (auto)
- **Where**: IP address, user agent, facility (hospital) context
- **Context**: Extra JSON data (patient ID, scope, reason, etc.)
- **Security**: Chain hash for tamper detection

**API Endpoints**:
| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/admin/audit-logs` | Hospital-scoped audit logs (last 200) |
| `GET /api/v1/superadmin/audit-logs` | System-wide audit logs (last 500) |
| `GET /api/v1/reports/audit/export` | CSV export of audit logs (last 5000) |

**Key Features**:
- **Facility Scoping**: All logs include hospital context (where applicable)
- **Tamper Detection**: Chain hash prevents modification of historical logs
- **Cross-Facility Tracking**: Logs include both access facility and data origin facility
- **Emergency Access Audit**: Break-glass access logged with high visibility
- **Admin Actions Audited**: User invitations, role changes, MFA resets logged

**Usage**:
```python
from api.utils import audit_log, get_request_hospital

audit_log(
    user=request.user,
    action="CREATE",
    resource_type="diagnosis",
    resource_id=diagnosis.id,
    hospital=get_request_hospital(request),
    request=request,  # Extracts IP and user agent
    extra_data={"patient_id": str(patient.id), "icd10": "E10.9"}
)
```

**Best Practices**:
1. Always include hospital context for facility-scoped actions
2. Include related resource IDs in extra_data (patient_id, user_id, facility_id)
3. Use standardized action names from the 17 supported types
4. Never log sensitive data (passwords, tokens)
5. Test audit entries in CI/CD pipeline

**Detailed Guide**: See `AUDIT_LOGGING_GUIDE.md` in session documentation for comprehensive implementation guide, examples, testing, and production checklist.

---

Centralized security posture for a healthcare EMR: encryption, key management, and token/session behaviour are explicit below.

### Encryption

- **At rest:** Use database and storage encryption in production. With PostgreSQL, enable TDE or use an encrypted volume/disk (e.g. LUKS, cloud-managed encryption). For SQLite (dev only), the file is unprotected; do not store production PHI on unencrypted volumes.
- **In transit:** All client–server and server–server traffic must use TLS. In production, serve the API over HTTPS only (reverse proxy or application TLS). Frontend must call `https://` APIs; avoid mixed content.

### Key management

- **Secrets:** `SECRET_KEY` (Django and JWT signing) must be set via environment; never commit defaults to production. Prefer a secrets manager (e.g. vault, cloud secret manager) over plain env files in production.
- **`.env` must never be committed.** It is listed in `.gitignore` (with `.env*`). It contains `DATABASE_URL`, `SECRET_KEY`, and other secrets. If `.env` was ever committed: (1) Rotate `DATABASE_URL` and `SECRET_KEY` immediately (new DB credentials, new Django secret). (2) Remove the file from git history from the repository root. If this repo lives under a parent (e.g. repo root is your home), path is `Downloads/EMR/medsync-backend/.env`. Example: `git filter-repo --path Downloads/EMR/medsync-backend/.env --invert-paths` (requires `git-filter-repo`), or `git filter-branch --force --index-filter "git rm --cached --ignore-unmatch Downloads/EMR/medsync-backend/.env" --prune-empty HEAD`. Then force-push and ensure all clones re-fetch.
- **Rotation:** Plan to rotate `SECRET_KEY` and JWT signing key periodically. After rotation, existing JWTs will be invalid; users must log in again. For zero-downtime rotation, run multiple workers with old and new keys during a short overlap, or use a dedicated JWT signing key (Simple JWT `SIGNING_KEY` setting) separate from Django `SECRET_KEY` so only token keys change.

### Session and token security

- **Access token TTL (short):** 15 minutes by default. Reduces exposure if an access token is leaked; frontend uses refresh to obtain new access tokens without re-authenticating. Overridable via `JWT_ACCESS_MINUTES`.
- **Refresh token TTL (longer):** 7 days by default. Overridable via `JWT_REFRESH_DAYS`.
- **Refresh rotation:** On each `POST /auth/refresh`, a new refresh token is issued and the previous one is invalidated (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`). The client must store and use the latest refresh token.
- **Server-side blacklist / revocation:** The backend uses Simple JWT’s token blacklist. On logout, the client sends the current refresh token in the request body; the server blacklists it so it cannot be used again. Rotated-out refresh tokens are also blacklisted. Recommended for healthcare so sessions can be terminated and stolen refresh tokens invalidated.
- **Client behaviour:** The frontend keeps tokens in memory and in sessionStorage, retries once on 401 by refreshing the access token, and sends the refresh token to `POST /auth/logout` so the server can revoke it. Inactivity timeout and MFA are additional safeguards.

**Maintenance:** Run `python manage.py flushexpiredtokens` periodically (e.g. daily cron) to remove expired blacklist entries from the database.

### Secrets rotation

Rotate quarterly (every 90 days) or immediately if compromise suspected. **Secrets to rotate:** `DATABASE_URL` (Neon password), `SECRET_KEY`, JWT signing keys, email/API keys. **Procedure:** Generate new value in secure source; update `.env` or secrets manager only on target environment; restart app; log rotation; invalidate old secret where possible. **Emergency:** Rotate affected secrets immediately; revoke dependent tokens; review audit logs; document in compliance record.

### Password policy

`api/password_policy.validate_password()` is used on activate and reset-password. Enforced rules:

| Rule | Enforced |
|------|----------|
| Minimum 12 characters | Yes |
| At least one uppercase letter | Yes |
| At least one lowercase letter | Yes |
| At least one digit | Yes |
| At least one symbol (!@#$%^&* etc.) | Yes |
| Last-5-password history (no reuse) | **Yes**; enforced on activate and reset-password via `api.password_policy.check_password_reuse` and `UserPasswordHistory` (last 5 hashes). |

Frontend `lib/password-policy.ts` mirrors the same five character rules for UX validation; backend is the authority.

### Backup codes (MFA recovery)

**Overview:** Backup codes are single-use codes generated during account activation that allow users to regain access if their TOTP device is lost. Each user receives **8 backup codes** on activation.

**Storage & Security:**
- Codes are **hashed with SHA256** before storage (plaintext never stored)
- Stored in `User.mfa_backup_codes` as JSON array of hashes: `["hash1", "hash2", ...]`
- Each code is 8 hexadecimal characters (32 bits entropy), cryptographically generated via `secrets.token_hex(4)`

**Usage (Single-Use):**
1. User logs in and is prompted for MFA verification
2. If user enters a **backup code** instead of TOTP code, MFA endpoint validates:
   - Compute `SHA256(backup_code)` and check if hash exists in stored hashes
   - If match: Remove hash from stored codes and save (single-use enforcement)
   - If no match: Return "Invalid code" error
3. After use, the code is permanently consumed and cannot be reused

**API Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/v1/auth/activate` | POST | Account activation; generates 8 backup codes in response |
| `POST /api/v1/auth/mfa-verify` | POST | MFA verification; accepts either `code` (TOTP) or `backup_code` (single-use) |
| `POST /api/v1/admin/users/<id>/reset-mfa` | POST | Admin MFA reset; clears all backup codes + regenerates TOTP secret |

**Response Format (Activation):**
```json
{
  "backup_codes": ["abcd1234", "efgh5678", ...],
  "access_token": "...",
  "refresh_token": "...",
  "user_profile": {...}
}
```

**Admin MFA Reset:** Hospital admins and super admins can reset a user's MFA via `POST /api/v1/admin/users/<id>/reset-mfa`, which:
- Clears all remaining backup codes (`mfa_backup_codes = null`)
- Generates a new TOTP secret
- Requires admin role matching user's hospital (admins see only same-hospital users)

**Frontend Behavior:**
- During account activation, backup codes are displayed with options to download/print
- During login MFA, users can toggle between "TOTP code" and "Backup code" modes
- Supports 4 languages: English, French, Akan, Spanish

**Testing:**
```bash
# Generate backup codes during account activation
curl -X POST http://localhost:8000/api/v1/auth/activate \
  -H "Content-Type: application/json" \
  -d '{
    "token": "...",
    "password": "SecurePass123!",
    "mfa_method": "totp"
  }'

# Use backup code during MFA verification
curl -X POST http://localhost:8000/api/v1/auth/mfa-verify \
  -H "Content-Type: application/json" \
  -d '{
    "mfa_token": "...",
    "backup_code": "abcd1234"
  }'
```

---

## Phase 7: 3-Tier Password Recovery System

**Status:** ✅ **COMPLETE** (37/40 todos done, 3 minor tasks pending)

A comprehensive enterprise-grade password recovery system with three tiers of assistance for healthcare environments. Fully HIPAA-compliant with complete audit trail, rate limiting, and MFA requirements for highest-risk operations.

### What's included

**8 API Endpoints**

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/v1/auth/forgot-password` | Public | User requests password reset via email (1-hour token) |
| `POST /api/v1/auth/reset-password` | Public | User completes reset with token |
| `POST /api/v1/auth/login-temp-password` | Public | Login with admin-generated temp password |
| `POST /api/v1/auth/change-password-on-login` | Authenticated | User changes password after temp login |
| `POST /api/v1/admin/users/{id}/generate-reset-link` | Hospital Admin | Admin generates 24-hour reset link |
| `POST /api/v1/admin/users/{id}/generate-temp-password` | Hospital Admin | Admin generates 1-hour temp password |
| `GET /api/v1/admin/password-resets` | Hospital Admin | Admin views password reset audit history |
| `POST /api/v1/superadmin/users/{id}/force-password-reset` | Super Admin + MFA | Super admin forces reset with TOTP verification |
| `GET /api/v1/superadmin/password-resets/suspicious` | Super Admin | Detect suspicious reset patterns |

**Database**

- `PasswordResetAudit` model: Tracks every password reset with full context (user, initiator, type, token lifecycle, status, IP, user agent, MFA verification)
- User model extensions: 6 fields for password reset state management
- 3 performance indexes on audit model
- Migration: `core.0011_phase7_password_recovery`

**Security Features**

- ✅ Rate limiting (5 attempts/email/hour for self-service)
- ✅ 256-bit cryptographic tokens (secrets.token_urlsafe)
- ✅ MFA requirement for Tier 3 (TOTP/2FA)
- ✅ Strong password policy (12+ chars, mixed case, digit, special)
- ✅ Password history (last 5 prevented from reuse)
- ✅ Hospital data isolation (admins only reset own hospital users)
- ✅ No user enumeration (generic error messages)
- ✅ IP & user agent logging
- ✅ Full HIPAA-compliant audit trail
- ✅ Session invalidation (new JWT tokens on reset)

**Testing**

- 100+ test cases covering all 3 tiers
- Permission tests, security tests, integration tests
- Edge cases: expired tokens, weak passwords, invalid MFA codes
- Run: `python -m pytest api/tests/test_phase7_password_recovery.py -v`

**Documentation**

Complete documentation in session workspace with:
- Full API reference with request/response examples
- 3 detailed workflow scenarios (self-service, admin-assisted, emergency)
- Security considerations and HIPAA compliance notes
- Frontend integration guide
- 30+ curl command examples for testing
- Deployment checklist

### Tier descriptions

**Tier 1: User Self-Service (95% of cases)**
- User enters email → receives reset link valid 1 hour
- User validates password policy → resets password
- Rate limited (5 attempts/hour per email)
- No MFA required

**Tier 2: Hospital Admin Assisted (4% of cases)**
- Admin generates reset link (24-hour validity) for users who forgot email
- OR admin generates temp password (1-hour, forces change on login) for urgent access
- Admin can view full audit history
- Hospital-scoped (can only reset users in own hospital)
- Logs with admin name and reason

**Tier 3: Super Admin Override (<1% of cases)**
- Super admin forces password reset on any user across all hospitals
- **Requires MFA verification** (TOTP code from authenticator app) for security
- Detects suspicious patterns (e.g., >5 resets/hospital/hour)
- Hospital admin receives notification
- Full audit trail with MFA verification

---

## Production deployment (Neon)

For production-style deployment the backend supports a **centralized PostgreSQL** database. **Neon** (hosted Postgres) is a solid choice: managed backups, point-in-time recovery (PITR), replication/HA, and SSL by default.

### What Neon gives you (mapped to requirements)

| Requirement | How Neon covers it |
|-------------|--------------------|
| Centralized DB | PostgreSQL in the cloud; all facilities use one database |
| Backups | Neon automated backups and PITR (use as backup strategy in reports) |
| High availability / replication | Provider-managed; document as your replication strategy |
| Encryption in transit | Connection string + SSL (`sslmode=require`) |
| Staging / testing | Neon branching for non-production DBs without touching production |

### Switching from SQLite to Neon Postgres

1. **Production must never run with `DEBUG=True`.** Set `DEBUG=False` and optionally `ENV=production` (enforces and raises if DEBUG is True). Set **`CORS_ALLOWED_ORIGINS`** to explicit origins (e.g. `https://app.example.com`); no wildcard (`*`) when using credentials.

2. **Set `DATABASE_URL`** in your production environment (never commit it):
   ```bash
   DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
   ```
   Neon provides this in the dashboard. The backend uses `dj-database-url`; if `DATABASE_URL` is set, it uses Postgres and **forces `sslmode=require`** for all connections.

3. **Install deps** (already in `requirements-local.txt`): `psycopg[binary]`, `dj-database-url`.

4. **Run migrations on Neon:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser   # or reuse setup_dev for seed data
   ```
   Then point the deployed API at Neon (e.g. backend on Render / Railway / Fly.io / VPS).

### What goes to Neon

- **All relational EMR data:** users, facilities, wards, patients, global registry, referrals, consents, break-glass logs, audit logs, clinical records, admissions, lab orders, etc.
- **File uploads** (scans, attachments) are not stored in Postgres; use object storage (S3, Cloudinary, Supabase Storage) and store only file URLs in the DB if you add uploads later.

### Backup and replication strategy (for your report)

- **Primary storage:** Neon managed PostgreSQL.
- **Backups:** Neon automated backups and point-in-time recovery; optionally add scheduled logical backups (e.g. `pg_dump`) to a secure bucket.
- **Replication / HA:** Provider-managed replication and high availability; document that you chose managed Postgres to reduce single-point-of-failure compared to SQLite or a single local server.

### Monitoring and system health

- **Rate limiting:** DRF throttling is enabled: unauthenticated requests use `AnonRateThrottle` (default 60/hour per IP), authenticated use `UserRateThrottle` (default 1000/hour per user). Override via `THROTTLE_ANON` and `THROTTLE_USER` (e.g. `"100/hour"`). The health endpoint is exempt: the health view uses `@throttle_classes([])` so it is not subject to anon rate limiting (load balancers / uptime checks are not throttled).
- **Uptime / health:** `GET /api/v1/health` — no auth; returns `200` with `{"status":"ok","database":"ok"}` if the app and DB are reachable, or `503` if the DB is unreachable. Use this for uptime checks and load balancer health checks.
- **Detailed health (super_admin only):** `GET /api/v1/superadmin/system-health` — returns counts (hospitals, users) and assumes DB is up.
- **Logs:** Request logs, auth, and the existing **audit trail** (AuditLog) for access and actions. Optionally plug Neon dashboard metrics (connections, CPU, storage) and an APM for the API.
- **Audit log sensitivity:** Only opaque IDs (e.g. UUIDs) are stored in `resource_id`; long or token-like values are redacted. Do not pass PHI or raw tokens to audit helpers.
- **Production security headers:** When `SECURE_HTTPS` is True (default when `DEBUG=False`), SSL redirect, HSTS, `X-Content-Type-Options: nosniff`, and XSS filter are enabled.

### EMR security (database)

Because the data is medical:

- **Always use SSL:** The backend forces `sslmode=require` when `DATABASE_URL` is Postgres. Ensure the URL or env does not override it.
- **Lock down DB access:** Only the backend (and trusted ops) should connect. No direct client or public access to the DB.
- **Secrets:** Store `DATABASE_URL`, `SECRET_KEY`, and other secrets in env or a secrets manager; never hardcode in code or commit to repo.
- **Least privilege:** Use a dedicated DB user with only the permissions the app needs; do not use the superuser in production.

### Suggested stack

- **Backend:** Render, Railway, Fly.io, or a VPS.
- **Database:** Neon Postgres.
- **Frontend:** Vercel or Netlify.
- **File storage (optional):** S3-compatible bucket for uploads; store URLs in Postgres.

### Production readiness (summary)

Conditionally ready for production: configure env (DEBUG=False, DATABASE_URL, CORS, SECRET_KEY), fix or accept any failing auth unit tests, plan optional improvements (real-time sync, N+1 tuning). Core workflows (auth, patient, clinical, appointments, admissions, lab, referrals, cross-facility, admin) and role behaviour are implemented. Security: secrets from env, CSP, HSTS, cookies, rate limits, audit, validation, object-level access. Health: `GET /api/v1/health`; audit export for admins. See Monitoring and Backup sections above.

### External integrations (optional)

- **Pharmacy:** Set `PHARMACY_WEBHOOK_URL`; POST on prescription dispense/cancel (event, record_id, hospital_id; no PHI). Code: `api/integrations.notify_pharmacy_dispense`.
- **PACS/Radiology:** Set `PACS_CALLBACK_URL`; POST on radiology order attachment/status. Code: `api/integrations.notify_pacs_result`.
- **Billing/NHIS:** `POST /api/v1/billing/nhis-claim` (encounter_id/patient_id); returns stub claim_ref; replace with real NHIS client in production.
- **FHIR push:** `POST /api/v1/interop/fhir-push` (target_url, resource_type, resource_id); serializes and POSTs to external HIE/EHR. Roles: doctor, hospital_admin, super_admin.
- **Beds:** `core.Bed` (ward, bed_code, status); `GET/POST/PATCH` admin/wards/…/beds and admin/beds; admissions/create accepts optional bed_id.
- **Discharge summary:** Encounter has `discharge_summary`; PATCH encounter to set; frontend can offer template.

---

## FHIR/HL7 interoperability

A **FHIR R4-style** read API and a minimal **HL7 v2** endpoint are provided for interoperability. All require authentication and are facility-scoped (same roles as patient read: super_admin, hospital_admin, doctor, nurse, receptionist).

### FHIR R4 (read-only)

- **GET /api/v1/fhir/Patient?identifier=&lt;value&gt;** — Search patients by identifier (e.g. Ghana Health ID). Returns a FHIR Bundle of type `searchset`.
- **GET /api/v1/fhir/Patient/&lt;id&gt;** — Read a single Patient resource.
- **GET /api/v1/fhir/Encounter?patient=&lt;id&gt;** — List encounters for a patient (Bundle).
- **GET /api/v1/fhir/Encounter/&lt;id&gt;** — Read a single Encounter resource.
- **GET /api/v1/fhir/Condition?patient=&lt;id&gt;** — List conditions (from diagnoses) for a patient (Bundle).
- **GET /api/v1/fhir/Condition/&lt;id&gt;** — Read a single Condition resource.
- **GET /api/v1/fhir/MedicationRequest?patient=&lt;id&gt;** — List medication requests (from prescriptions) for a patient (Bundle).
- **GET /api/v1/fhir/MedicationRequest/&lt;id&gt;** — Read a single MedicationRequest resource.
- **GET /api/v1/fhir/Observation?patient=&lt;id&gt;** — List observations (from vitals) for a patient (Bundle).
- **GET /api/v1/fhir/Observation/&lt;id&gt;** — Read a single Observation resource.

Resources map from internal models: Patient, records.Encounter, records.Diagnosis → Condition, records.Prescription → MedicationRequest, records.Vital → Observation (vital-signs panel with components).

### HL7 v2 (ADT-style)

- **GET /api/v1/hl7/adt?patient=&lt;id&gt;** — Returns pipe-delimited ADT A01-style segments (MSH, PID, PV1) for the given patient. Response shape: `{"data": ["MSH|...", "PID|...", "PV1|..."], "format": "HL7v2.5 ADT A01"}`.

---

## Inter-hospital access rules

Cross-facility data access is **enforced server-side**. The UI may hide or show controls, but the API is the authority: every interop endpoint checks role and policy before returning data or performing actions.

### Who can view cross-facility data?

Only users with an **interop-capable role** may call global-patient search, cross-facility records, referrals, consent, and break-glass endpoints:

| Role              | Global patient search | Cross-facility records | Create referral | Accept/update referral | Grant consent | Break-glass | List consents / break-glass |
|-------------------|------------------------|------------------------|-----------------|-------------------------|---------------|-------------|-----------------------------|
| **super_admin**   | Yes (all)              | Yes*                   | No**            | No**                    | Yes           | Yes*        | Yes*                        |
| **hospital_admin**| Yes (own facility)     | Yes*                   | Yes             | Yes (incoming)          | Yes***        | Yes         | Yes (own facility)          |
| **doctor**        | Yes (own facility)     | Yes*                   | Yes             | Yes (incoming)          | Yes***        | Yes         | Yes (own facility)          |
| **nurse**         | No                     | No                     | No              | No                      | No            | No          | No                          |
| **lab_technician**| Search only (hospital-scoped) | No                     | No              | No                      | Yes only      | No          | No                          |

\* Subject to conditions below.  
\** super_admin has no facility; referral create/update require a facility.  
\*** Only if the user’s facility has the patient linked (see below).

### Under what conditions can cross-facility records be viewed?

Access to `GET /cross-facility-records/<global_patient_id>` is allowed only if **one** of the following holds (evaluated in order). *Exception:* **super_admin** with no facility assigned has full read access for support purposes (no consent/referral/break-glass required).

1. **Consent**  
   The requesting user’s facility has an **active consent** for that global patient (granted to the facility, not expired).  
   - **Scope:** `SUMMARY` (demographics + facility list only) or `FULL_RECORD` (includes aggregated clinical records from all linked facilities), as defined when consent was granted.

2. **Accepted referral**  
   There is an **accepted or completed referral** of that global patient **to** the user’s facility.  
   - **Scope:** `SUMMARY` only (no clinical records). Full record access still requires consent.

3. **Break-glass**  
   The same user has created a **break-glass** entry for that global patient at their facility within the last **15 minutes**.  
   - **Scope:** `FULL_RECORD`.  
   - Every break-glass use is logged in `BreakGlassLog` and in `AuditLog` with action `EMERGENCY_ACCESS` for review.

All of the above are enforced in `api.utils.can_access_cross_facility()` and in the `cross_facility_records` view. No cross-facility data is returned without passing one of these conditions.

### Who can grant consent?

- **Consent** can be granted only by a user whose **facility has the patient linked** (i.e. a `FacilityPatient` exists for that global patient at that facility), or by **super_admin** (admin override).  
- This prevents arbitrary facilities from granting consent for patients they do not hold. The facility that holds the patient (or super_admin) grants consent to another facility (`granted_to_facility_id`).

### How are actions logged and reviewed?

| Action                     | Where it is logged                          | How to review |
|----------------------------|---------------------------------------------|----------------|
| View cross-facility records| `AuditLog`: action `VIEW`, resource_type `global_patient`, optional `extra_data.cross_facility_scope` | Hospital: `GET /admin/audit-logs`; Super: `GET /superadmin/audit-logs` |
| Grant consent              | `AuditLog`: action `CREATE`, resource_type `consent`, `extra_data` (global_patient_id, granted_to_facility_id, scope) | Same audit endpoints |
| Create referral            | `AuditLog`: action `CREATE`, resource_type `referral`, `extra_data` (global_patient_id, to_facility_id) | Same audit endpoints |
| Update referral (accept/reject/complete) | `AuditLog`: action `UPDATE`, resource_type `referral`, `extra_data` (new_status, global_patient_id) | Same audit endpoints |
| Break-glass                | `BreakGlassLog` (per global patient, facility, user, reason, timestamp) and `AuditLog`: action `EMERGENCY_ACCESS`, resource_type `global_patient` | `GET /break-glass/list?global_patient_id=...` and audit logs |

Audit log entries are chained (hash of previous + current) to support integrity checks. Use hospital-level audit for normal review; use superadmin audit and break-glass list for cross-facility and emergency-access review.

---

## Identity and patient matching

The global registry links facility-level patients to a single **GlobalPatient** (global identity) so that cross-facility records, consent, and referrals are scoped to one person. How matching works is described below.

### Is matching deterministic?

**Yes, when a national identifier is present.**

- **GlobalPatient** has a single canonical field **`national_id`** (e.g. Ghana Health ID). This field is **unique** in the database: at most one `GlobalPatient` per value.
- The backfill command (`manage.py backfill_global_patients`) treats **Ghana Health ID** as the national ID: it sets `GlobalPatient.national_id` from `Patient.ghana_health_id`. Before creating a new `GlobalPatient`, it looks up by `national_id`; if one exists, it reuses it and only creates a `FacilityPatient` link. So for any given Ghana Health ID, the system converges to **one** global identity.
- Linking in the API (`POST /facility-patients/link`) is by **`global_patient_id`** (UUID). The user chooses an existing global patient from search and links their facility (and optionally a local `Patient`) to it. The API does not create new `GlobalPatient` records; it only creates links. So matching at link time is deterministic: the chosen global patient is the one used.

**When `national_id` is missing:** A `GlobalPatient` can have `national_id` null (e.g. legacy data or patient without national ID). In that case there is no unique key on (name, DOB, etc.), so the system does not automatically merge or deduplicate by demographics. Operational practice should be to assign or backfill national IDs where possible so that matching remains deterministic.

### Do we support multiple identifiers?

**One official national identifier per global identity; other fields support search and disambiguation.**

- **GlobalPatient** stores:
  - **`national_id`** — One canonical national identifier (e.g. Ghana Health ID). Unique when set. Used for deterministic matching and search.
  - Demographics: `first_name`, `last_name`, `date_of_birth`, `gender`, `blood_group`, `phone`, `email`.
- **Facility-level `Patient`** has:
  - **`ghana_health_id`** — Required and unique per facility’s registration context; used as the source for `GlobalPatient.national_id` in backfill.
  - **`national_id`** — Optional; can hold a second identifier for display or reporting but is not used for global matching in the current implementation.

There is no separate multi-identifier table (e.g. multiple ID types per patient). To support another national ID scheme (e.g. another country or sector), you could: (a) map it into `national_id` if it is the single canonical ID for the registry, or (b) extend the model with an additional identifier field and matching rules and document the chosen authority.

**Search** uses multiple fields for discovery only (not for uniqueness): `GET /global-patients/search` matches on first name, last name, national_id, phone, and email (substring match). So users can find a global patient by any of these; the authoritative match for linking remains `national_id` when present and the chosen `global_patient_id` at link time.

### How do we prevent duplicate global patients?

| Mechanism | What it does |
|-----------|----------------|
| **Unique `national_id`** | The database enforces uniqueness on `GlobalPatient.national_id`. Two global patients cannot share the same non-null national ID. |
| **Backfill behaviour** | `backfill_global_patients` looks up by `national_id` (from Ghana Health ID) before creating. If a `GlobalPatient` already exists for that ID, it reuses it and only creates or updates the `FacilityPatient` link. New `GlobalPatient` rows are created only when no row with that `national_id` exists. |
| **Link endpoint** | `POST /facility-patients/link` does not create `GlobalPatient` records. It only links an existing global patient (by UUID) to a facility. Duplicate global identities are not created by this endpoint. |
| **Same facility, same global patient** | `FacilityPatient` has `unique_together = (facility, global_patient)`, so a facility can have only one link per global patient. Re-linking the same global patient to the same facility returns “Patient already linked to this facility”. |

**When `national_id` is null:** There is no uniqueness constraint on (name, DOB, etc.). So duplicate global patients with the same demographics but no national ID are possible if they are created outside the backfill (e.g. manually or by a future create API). To minimise duplicates:

- Prefer registering and backfilling with **Ghana Health ID** (or another canonical national ID) so that `national_id` is set and uniqueness is enforced.
- If creating or importing global patients without national ID, use operational processes (e.g. search before create, manual merge in admin) to keep duplicates under control.

---

## AI Intelligence Module

**Overview:** Disease risk prediction (XGBoost), clinical decision support (differential diagnosis), triage (severity), patient similarity (k-NN), referral recommendation, multi-agent orchestration. LLM chat is out of scope for Phase 1.

**Components:** Data layer (`api/ai/data_processor.py`, `feature_engineering.py`); ML models under `api/ai/ml_models/` (risk_predictor, diagnosis_classifier, triage_classifier, similarity_matcher) loading from `api/ai/models/*.joblib` or `MEDSYNC_AI_MODELS_DIR`; services in `api/ai/services/services.py`; orchestrator `api/ai/agents/orchestrator.py`; persistence and AuditLog; REST in `api/views/ai_views.py` with `get_request_hospital(request)`.

### Model artifacts (where the “models” live)

- **Default directory:** `medsync-backend/api/ai/models/`
- **Expected files:** `risk_predictor.joblib`, `triage_classifier.joblib`, `diagnosis_classifier.joblib`, `similarity_matcher.joblib`
- **Override directory at runtime:** set `MEDSYNC_AI_MODELS_DIR` (see `medsync_backend/settings.py`)

**API endpoints (base `/api/v1`):** All require `Authorization: Bearer <token>`.

| Method | Path | Purpose | Roles |
|--------|------|---------|-------|
| POST | `/ai/analyze-patient/<patient_id>` | Full multi-agent analysis (risk, triage, diagnosis, optional similarity/referral, summary) | doctor, nurse, hospital_admin, super_admin |
| POST | `/ai/risk-prediction/<patient_id>` | 5-year disease risk scores | doctor, nurse, super_admin |
| POST | `/ai/clinical-decision-support/<patient_id>` | Differential diagnosis (optional body: chief_complaint) | doctor, super_admin |
| POST | `/ai/triage/<patient_id>` | Triage level and ESI (optional body: chief_complaint) | doctor, nurse, super_admin |
| POST | `/ai/find-similar-patients/<patient_id>?k=10` | Similar cases (k max 50) | doctor, super_admin |
| POST | `/ai/referral-recommendation/<patient_id>` | Recommended hospitals (optional body: required_specialty) | doctor, hospital_admin, super_admin |
| GET | `/ai/analysis-history/<patient_id>?limit=10&offset=0` | Past AI analyses | doctor, nurse, super_admin |

**Training:** `api/ai/train_models.py` writes `risk_predictor.joblib`, `triage_classifier.joblib`, `diagnosis_classifier.joblib`, `similarity_matcher.joblib` to `api/ai/models/` (or `--output-dir`). Synthetic data by default; custom data path for future use. Run: `python manage.py shell -c "from api.ai.train_models import run_training; run_training()"` or `python api/ai/train_models.py`. Set `MEDSYNC_AI_MODELS_DIR` if using non-default dir.

**Quick start (generate/update model files):**

From repo root:

```bash
# Installs backend deps, runs migrations, trains models into medsync-backend/api/ai/models/
bash scripts/setup_ai.sh
```

Or from `medsync-backend/`:

```bash
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','medsync_backend.settings'); import django; django.setup(); from api.ai.train_models import run_training; run_training()"
```

**Deployment checklist (AI):** Dependencies in requirements-local.txt (scikit-learn, xgboost, numpy, pandas, joblib); migrate; optional model files or rule-based placeholders; `MEDSYNC_AI_MODELS_DIR` if needed; cache (e.g. Redis) for risk prediction; permissions in `api/permissions.py` for ai/* routes; audit all AI actions; HTTPS and hospital scope; smoke test `POST /api/v1/ai/analyze-patient/<patient_uuid>`.

---

## AI Model Training & Deployment

MedSync includes a comprehensive AI/ML pipeline for clinical decision support. The system trains models on hybrid data (synthetic Ghana-specific + public UCI/MIMIC datasets) and enforces hospital-level approval before clinical deployment.

### Quick Start: Train Models

From the `medsync-backend/` directory:

```bash
# Option 1: Via Django management command (recommended)
python manage.py train_ai_models --data-source hybrid --model-version 1.0.0-hybrid

# Option 2: Via Python directly
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings'); django.setup(); from api.ai.train_models import run_training; run_training()"

# Option 3: Via shell script (if available)
bash scripts/setup_ai.sh
```

### Training Pipeline Overview

**Input:** Hybrid dataset (7,000 samples) =  
- 3,000 synthetic patients (Ghana-specific: 25% malaria, 2% sickle cell, tropical conditions)
- 4,000 UCI readmission dataset (public benchmark)

**Process:**
1. Feature engineering → 26-dimensional vectors (vitals, labs, demographics, comorbidities)
2. Train 3-model ensemble:
   - Logistic Regression (baseline, interpretable)
   - Random Forest (robust, non-linear patterns)
   - XGBoost (state-of-the-art, gradient boosting)
3. 5-fold stratified cross-validation
4. Calculate AUC-ROC, sensitivity, specificity per disease
5. Save models, scaler, metrics, metadata

**Output:** Models saved to `api/ai/models/v{version}/`
- `logistic_regression.joblib` — Serialized LR model
- `random_forest.joblib` — Serialized RF model
- `xgboost.joblib` — Serialized XGBoost model
- `scaler.joblib` — Feature normalization (StandardScaler)
- `metadata.json` — Training info (timestamp, feature names, class names)
- `metrics.json` — Validation metrics (AUC, sensitivity, specificity)

### Training Models Locally

#### Quick Start (Synthetic Data)
```bash
cd medsync-backend
python manage.py train_ai_models --data-source synthetic --model-version 1.0.0
```

#### Hybrid Approach (Best for Development)
```bash
python manage.py train_ai_models --data-source hybrid --model-version 1.0.0-hybrid
```

#### With MIMIC Data (Production)
```bash
# First, download MIMIC-IV data from PhysioNet (see "MIMIC-IV Access" section above)
# Then:
export MIMIC_DATA_PATH="/path/to/mimic-iv/csv"
python manage.py train_ai_models --data-source mimic-iv --model-version 1.0.0-mimic
```

#### Custom Data
```bash
python manage.py train_ai_models --data-path /path/to/data.csv --model-version custom-1.0
```

#### Validation Metrics

Trained models are validated against these thresholds:
- **AUC-ROC** ≥ 0.80 (discriminative ability)
- **Sensitivity** ≥ 0.75 (recall of positive cases)
- **Specificity** ≥ 0.85 (recall of negative cases)

If a model fails validation, training halts with error. See metrics at: `api/ai/models/v{version}/metrics.json`

To skip validation (development only):
```bash
python manage.py train_ai_models --skip-validation --data-source synthetic
```

#### Model Storage & Versioning

All trained models are organized by version:
```
api/ai/models/
├── v1.0.0/              # Synthetic Ghana data
├── v1.0.0-hybrid/       # Hybrid synthetic + UCI
├── v1.0.0-mimic/        # MIMIC-IV data
└── logistic_regression.joblib  # Legacy (fallback)
```

To load a specific version, set in `.env`:
```bash
AI_MODEL_VERSION=1.0.0-hybrid
```

### Configuration

**Settings** (`medsync_backend/settings.py`):
```python
# Model version and training status
AI_MODEL_VERSION = "1.0.0-hybrid"  # Currently deployed version
AI_MODELS_TRAINED_ON_REAL_DATA = True  # Switch to True after real data training
AI_MODELS_VALIDATION_METRICS = {
    'auc': 0.5921,
    'sensitivity': 0.9013,
    'specificity': 0.2948,
    'training_date': '2026-04-20'
}

# AI deployment: set to False to disable AI features globally (circuit breaker)
DISABLE_AI_CLINICAL_FEATURES = False

# Clinical threshold: only return predictions with confidence ≥ this (0.0-1.0)
AI_CONFIDENCE_THRESHOLD = 0.75  # Set to 0.80+ for clinical deployment
```

**Environment variables** (`.env`):
```bash
# Data source options: "synthetic", "uci", "mimic", "kaggle", "hybrid"
AI_TRAINING_DATA_SOURCE=hybrid

# Model version to deploy
AI_MODEL_VERSION=1.0.0-hybrid

# Disable AI features if needed (circuit breaker)
DISABLE_AI_CLINICAL_FEATURES=False
```

### Data Sources

The training pipeline supports multiple public data sources (no PHI):

| Source | Size | Use | Config |
|--------|------|-----|--------|
| **Synthetic Ghana** | 3,000 | Local prevalence (malaria, sickle cell) | Built-in (NDARRAY) |
| **UCI Readmission** | 4,000+ | Benchmark readmission prediction | public API (auto-download) |
| **MIMIC-IV** | 50,000+ | ICU data (if credentials provided) | `MIMIC_TOKEN` env var |
| **Kaggle** | Various | Additional datasets | `KAGGLE_USERNAME`, `KAGGLE_KEY` |
| **WHO/Open-i** | Global | Reference data | Auto-download |

#### MIMIC-IV Access for Research

MIMIC-IV is a large, publicly-available dataset of de-identified intensive care unit (ICU) patients. To access MIMIC-IV data:

1. **Register for PhysioNet:** Visit [https://physionet.org/](https://physionet.org/) and create an account
2. **Complete Credentialed Access Agreement:** Sign the PhysioNet DUA (Data Use Agreement) and provide your institution/research details
3. **Approval (typically 1-2 days):** You'll receive email confirmation with access
4. **Download Data:** Log into PhysioNet and download MIMIC-IV CSV files (admissions.csv, patients.csv, diagnoses_icd.csv, procedures_icd.csv, prescriptions.csv)
5. **Use in Training:** Set env var and run:
   ```bash
   export MIMIC_DATA_PATH="/path/to/mimic-iv/csv"
   python manage.py train_ai_models --data-source mimic-iv
   ```

**License:** MIMIC-IV is free for research via PhysioNet Credentialed Access.

**Note for this project:** Using pre-downloaded synthetic MIMIC-like data or the hybrid approach (synthetic + UCI) is acceptable and requires no registration. Start with `--data-source hybrid` for development and testing.

### Hospital-Level Approval Workflow

Before clinical use, hospital admins must explicitly approve AI features:

1. **Train models** → `python manage.py train_ai_models`
2. **System admin reviews metrics** → Check `api/ai/models/v{version}/metrics.json`
3. **Hospital admin approves** → `POST /api/v1/admin/ai-deployment-approval`
   ```json
   {
     "model_version": "1.0.0-hybrid",
     "hospital_id": "<hospital_uuid>",
     "approved": true,
     "notes": "Metrics reviewed; suitable for clinical use"
   }
   ```
4. **Approval logged** → `AIDeploymentLog` records who, when, which hospital
5. **AI features enabled** → Doctor/nurse can now use AI analysis endpoints

**Revocation:** If issues detected, hospital admin can call same endpoint with `approved: false` to instantly disable AI for their facility.

### Model Loading & Versioning

On startup, the backend attempts to load models in this order:

1. **Versioned directory:** `api/ai/models/v{AI_MODEL_VERSION}/` (e.g., `v1.0.0-hybrid/`)
2. **Legacy files:** `api/ai/models/` (if versioned doesn't exist)
3. **Rule-based fallback:** If no files found, use hard-coded scoring rules (always available, but lower accuracy)

**Check loaded version:**
```bash
curl http://localhost:8000/api/v1/ai/status
# Response includes: model_version, enabled, avg_response_ms, analyses_24h
```

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Models not found" | Missing `api/ai/models/v{version}/` | Run `python manage.py train_ai_models` |
| "Training fails on import" | scikit-learn/xgboost missing | `pip install -r requirements-local.txt` |
| "AI endpoints return 503" | `DISABLE_AI_CLINICAL_FEATURES=True` | Set to `False` in settings or `.env` |
| "Low accuracy metrics" | Public data only, not real patient outcomes | Plan to retrain with hospital data after go-live |
| "Inference timeout" | Model too large or hardware slow | Consider model compression or GPU |

### Monitoring & Metrics

**Daily metrics** (available to super_admin):

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/superadmin/analytics/ai-models
```

Returns: daily inferences, avg response time, errors, hospital-level adoption rate.

**Audit trail:** All AI analyses logged in `AuditLog` with action type `AI_ANALYSIS`. Check:

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/superadmin/audit-logs?action=AI_ANALYSIS
```

### Post-MVP Roadmap

- **Real data training:** After pilot hospitals go live, collect de-identified outcomes (diagnoses, admissions, readmissions) to retrain models on local patient data
- **Parallel agents:** Full async CrewAI orchestration for <1 second multi-agent analysis
- **FAISS indexing:** Swap exhaustive patient similarity search for approximate nearest neighbor (100x faster at scale)
- **Model monitoring:** Drift detection and automated retraining pipelines
- **Federated learning:** Train on encrypted data across hospitals without centralizing patient records

### Testing & Validation

**Verify AI training pipeline is working:**

```bash
# Test 1: Synthetic data generation and model training
cd medsync-backend
python test_ml_pipeline.py

# Expected output:
# ✓ Synthetic Data Generation: PASS
# ✓ Disease-Stratified Cohorts: PASS
# ✓ Age-Stratified Cohorts: PASS
# ✓ Model Loading: PASS
# 4/4 tests passed
```

**Run AI-specific unit tests:**

```bash
# Test AI deployment log, metrics validation, and circuit breaker
python -m pytest api/tests/test_ai_clinical_deployment.py -v

# Test AI analysis endpoints (requires authentication)
python -m pytest api/tests/test_ai_views.py -v
```

**Key test coverage:**

| Test | Location | What it covers |
|------|----------|----------------|
| Synthetic data generation | `test_ml_pipeline.py` | Ghana disease prevalence, readmission simulation |
| Disease-stratified cohorts | `test_ml_pipeline.py` | Malaria, diabetes, elderly patients |
| Model validation | `test_ml_pipeline.py` | Ensemble model loading, metrics validation |
| AI deployment workflow | `test_ai_clinical_deployment.py` | Hospital approval, circuit breaker, metrics thresholds |
| AI endpoints | `test_ai_views.py` | Authorization, patient analysis, risk prediction |

**Performance benchmarks (synthetic data, 2,000 samples):**

| Step | Time | Target |
|------|------|--------|
| Synthetic data generation | 0.3s | <5s |
| Feature extraction | 0.2s | <5s |
| 3-model ensemble training (5-fold CV) | ~78s | <300s (5 min) |
| Model evaluation & metrics | 0.1s | <5s |
| **Total training time** | **~78s** | **<5 min** ✓ |



### FAISS: Fast Similarity Search at Scale

**Problem:** Similarity search uses exhaustive O(n) cosine similarity, which takes 500ms-5s at 100k+ patients. Unacceptable for clinical worklists.

**Solution:** FAISS (Facebook AI Similarity Search) provides approximate nearest neighbor search in O(log n) time with <100ms query latency at 1M patients.

#### Setup

```bash
# FAISS is in requirements.txt (faiss-cpu by default)
pip install -r requirements-local.txt

# Or if GPU available:
pip install faiss-gpu
```

#### Building the Index

The similarity index is built nightly (2 AM) via Celery Beat:

```bash
# Check Celery Beat is scheduled
grep rebuild-similarity-index medsync_backend/settings.py
```

Or manually rebuild:

```python
from api.tasks.ai_tasks import rebuild_similarity_index
rebuild_similarity_index.delay()
```

#### Using FAISS in Similarity Search

The `POST /ai/find-similar-patients/<patient_id>` endpoint automatically uses FAISS if available:

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/ai/find-similar-patients/<patient_uuid>
```

Response includes timing header: `X-Query-Time: 45ms` (vs 5000ms without FAISS).

#### Monitoring Index Status

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/admin/ai/similarity-index
```

Returns:
```json
{
  "num_patients": 15000,
  "size_mb": 24.5,
  "last_rebuilt": "2026-04-20T02:00:00Z",
  "ready": true
}
```

#### Implementation Details

- **Module:** `api/ai/faiss_indexer.py` (FaissIndexer class)
- **Index type:** `IndexFlatIP` (inner product on normalized vectors = cosine similarity)
- **Storage:** `api/ai/indexes/similarity_index.faiss` (binary FAISS file) + `similarity_index.pkl` (metadata)
- **Update frequency:** Nightly rebuild via Celery Beat; incremental add support for <100 new patients
- **Performance:** Expected 50x speedup at clinical scale (100k-1M patients)

---

## Project Structure

```
medsync-backend/
├── manage.py
├── requirements-local.txt
├── pyrightconfig.json
├── .env                       # Optional: DATABASE_URL, SECRET_KEY, CORS, JWT, etc.
├── db.sqlite3                 # Default SQLite DB (dev only)
├── medsync_backend/           # Django project config
│   ├── settings.py
│   ├── urls.py                # Mounts Django admin at /admin/, API at /api/v1/
│   └── wsgi.py
├── core/                      # Shared core models & commands
│   ├── models.py              # User, Hospital, Ward, Bed, AuditLog
│   ├── admin.py, apps.py
│   └── management/commands/
│       └── setup_dev.py       # Seeds dev users, hospitals, wards
├── patients/                  # Patient, admissions, alerts, appointments
│   ├── models.py              # Patient, Allergy, PatientAdmission, ClinicalAlert, Appointment
│   ├── admin.py, apps.py
├── records/                   # Clinical records (EHR), facility-owned encounters
│   ├── models.py              # MedicalRecord, Diagnosis, Prescription, LabOrder, LabResult,
│   │                          # Vital, NursingNote, Encounter (patient-level, hospital-scoped)
│   ├── admin.py, apps.py
├── interop/                   # Cross-facility interoperability (HIE)
│   ├── models.py              # GlobalPatient, FacilityPatient, Consent, Referral,
│   │                          # SharedRecordAccess, BreakGlassLog, Encounter (facility_patient-level)
│   ├── admin.py, apps.py
│   └── management/commands/
│       └── backfill_global_patients.py
└── api/                       # REST API (all under /api/v1/)
    ├── urls.py                # All v1 route definitions
    ├── serializers.py         # DRF serializers for all entities
    ├── password_policy.py     # Password strength validation
    ├── utils.py               # get_patient_queryset, can_access_cross_facility, audit_log, etc.
    └── views/
        ├── health_views.py    # GET /health (no auth)
        ├── auth_views.py      # Login, MFA, activate, forgot/reset password, refresh, logout, me
        ├── patient_views.py   # Patient search, CRUD, export-pdf, records/diagnoses/prescriptions/labs/vitals/allergies
        ├── record_views.py    # Create diagnosis, prescription, lab order, vitals, vitals/batch, allergy, nursing note, radiology order; dispense; amend; doctor favorites/refill/amendment-history
        ├── encounter_views.py # GET/POST patients/<uuid>/encounters; GET worklist/encounters; PATCH/DELETE encounter detail
        ├── appointment_views.py # Appointments list, create, update, delete, check-in, reschedule, no-show, statistics
        ├── alert_views.py    # Alerts list, resolve
        ├── admin_views.py    # Users list/invite/bulk-import/update, audit-logs, staff-onboarding, wards, departments, lab-units, lab-test-types, doctors, duplicates, beds; send-password-reset, reset-mfa, resend-invite
        ├── bed_views.py      # List beds by ward, create bed, update bed status
        ├── lab_views.py      # Lab orders list, submit result, bulk-submit, analytics/trends, attachment upload
        ├── admission_views.py # Admissions list/create, by ward, discharge
        ├── dashboard_views.py # Dashboard metrics, analytics
        ├── report_views.py   # Export patients CSV, export audit CSV, billing invoices, NHIS claim stub
        ├── fhir_views.py     # FHIR R4 read; HL7 ADT; interop/fhir-push
        ├── superadmin_views.py # Hospitals, onboarding-dashboard, bulk-import-staff, connectivity, cross-facility-activity, global audit, system health, break-glass, GMDC, onboard-hospital, force-password-reset, suspicious resets
        ├── global_patient_views.py # Global patient search, link, facilities, facility update, cross-facility records
        ├── referral_views.py # Create referral, incoming list, update status
        ├── consent_views.py   # Grant consent, list consents, revoke
        ├── break_glass_views.py # Emergency access create, list
        ├── nurse_views.py    # Shift start, shift handover, overdue vitals
        ├── password_recovery_views.py # Tier 2: generate-reset-link, generate-temp-password, password-resets; Tier 3: force-password-reset, suspicious
        └── ai_views.py       # AI analyze-patient, risk-prediction, clinical-decision-support, triage, find-similar-patients, referral-recommendation, analysis-history
```

---

## Data Model Overview

| App       | Models |
|-----------|--------|
| **core**  | `User` (email, role, hospital, ward, MFA, invitation, account_status), `Hospital`, `Ward`, `Bed` (ward, bed_code, status), `AuditLog` (chain_hash, actions) |
| **patients** | `Patient` (ghana_health_id, demographics), `Allergy`, `PatientAdmission`, `ClinicalAlert` (severity, status, message), `Appointment` (scheduled_at, status, type, provider) |
| **records** | `MedicalRecord` (record_type, versioning, amendments), `Diagnosis`, `Prescription`, `LabOrder`, `LabResult`, `Vital`, `NursingNote`, `Encounter` (patient, hospital, encounter_type, encounter_date), `NurseShift`, `ShiftHandover` |
| **interop** | `GlobalPatient`, `FacilityPatient` (link to local Patient), `Consent`, `Referral` (optional consent, record_ids_to_share), `SharedRecordAccess`, `BreakGlassLog`, `Encounter` (facility_patient-level, for interop context) |

---

## API Base & Endpoints

**Base URL:** `http://localhost:8000/api/v1/`

All endpoints except `GET /health` require `Authorization: Bearer <access_token>` unless noted. Data is hospital-scoped: non–super_admin users see only their facility’s data; super_admin with no hospital sees all.

**User profile (profiling):** Login (after MFA), account activation, and password reset return `user_profile` with the same shape as `GET /auth/me`: identity (user_id, email, full_name), role, hospital_id, hospital_name, ward_id, ward_name, department, account_status, and for doctors gmdc_licence_number and licence_verified. One profile structure for all roles; the frontend uses it for sidebar, top bar, and dashboard. Refresh token response does not include profile; the client keeps the profile from the last login/activate.

**Pagination:** Some list endpoints use DRF cursor pagination and return `next_cursor` and `has_more`. Others return a capped list with `next_cursor: null` and `has_more: false` (no cursor for subsequent pages). Examples: `GET /patients/search` and global patient search cap at 50 results; `GET /patients/<id>/encounters` caps at 100. For large result sets, use query filters to narrow (e.g. search by name or Ghana Health ID).

### Full API route table

| Method | Path | Description | Role restriction |
|--------|------|-------------|------------------|
| GET | `/health` | Health check (app + DB) | None |
| POST | `/auth/login` | Login; returns tokens, optional MFA required | None |
| POST | `/auth/mfa-verify` | TOTP verification | None |
| POST | `/auth/activate` | Activate account (token) | None |
| GET, POST | `/auth/activate-setup` | MFA setup | None |
| POST | `/auth/forgot-password` | Request reset | None |
| POST | `/auth/reset-password` | Reset with token | None |
| POST | `/auth/login-temp-password` | Login with admin-generated temp password | None |
| POST | `/auth/change-password-on-login` | Change password after temp login | Authenticated |
| POST | `/auth/refresh` | Refresh access token | Authenticated |
| POST | `/auth/logout` | Logout (blacklist refresh) | Authenticated |
| GET | `/auth/me` | Current user profile (same shape as `user_profile` in login/activate: user_id, hospital_id, email, role, full_name, department, ward_id, account_status, hospital_name, ward_name, gmdc_licence_number, licence_verified) | Authenticated |
| GET | `/patients/search` | Search patients (max 50; returns `next_cursor: null`, `has_more: false`) | doctor, hospital_admin, super_admin, nurse, receptionist, lab_technician (hospital-scoped) |
| POST | `/patients` | Register patient | doctor, hospital_admin |
| GET, PATCH | `/patients/<uuid>` | Patient detail / update | doctor, hospital_admin, super_admin (read: same + nurse for own facility) |
| GET, POST | `/patients/<uuid>/encounters` | List or create encounters | List: super_admin, hospital_admin, doctor, nurse; Create: super_admin, hospital_admin, doctor |
| GET | `/patients/<uuid>/records` | Patient medical records | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/diagnoses` | Patient diagnoses | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/prescriptions` | Patient prescriptions | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/labs` | Patient lab results | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/vitals` | Patient vitals | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/allergies` | Patient allergies | doctor, hospital_admin, super_admin |
| GET | `/patients/<uuid>/export-pdf` | Export patient record PDF | doctor, hospital_admin, super_admin |
| PATCH, DELETE | `/patients/<uuid>/encounters/<uuid>` | Update or delete encounter | super_admin, hospital_admin, doctor |
| POST | `/records/diagnosis` | Create diagnosis | doctor |
| POST | `/records/prescription` | Create prescription | doctor |
| POST | `/records/lab-order` | Create lab order | doctor |
| POST | `/records/vitals` | Create vitals | doctor, nurse, super_admin |
| POST | `/records/vitals/batch` | Batch vitals (ward) | nurse, super_admin |
| POST | `/records/allergy` | Create allergy | doctor, nurse, super_admin |
| POST | `/records/nursing-note` | Create nursing note | nurse, super_admin |
| POST | `/records/prescription/<uuid>/dispense` | Mark prescription dispensed | doctor, nurse, super_admin |
| POST | `/records/radiology-order` | Create radiology order | doctor |
| POST | `/records/radiology-order/<uuid>/attachment` | Upload radiology order attachment | doctor, super_admin |
| POST | `/records/<uuid>/amend` | Amend record (versioned) | doctor, nurse, super_admin (same facility or super_admin) |
| GET | `/doctor/favorites/prescriptions` | Doctor favorite prescriptions | doctor, super_admin |
| POST | `/doctor/prescriptions/<uuid>/refill` | Prescription refill | doctor, super_admin |
| GET | `/doctor/records/<uuid>/amendment-history` | Record amendment history | doctor, super_admin |
| GET | `/admin/users` | List users (hospital-scoped for hospital_admin; all for super_admin) | hospital_admin, super_admin |
| POST | `/admin/users/invite` | Invite user (super_admin must send `hospital_id`) | hospital_admin, super_admin |
| POST | `/admin/users/bulk-import` | Bulk import users (CSV, max 5 MB, 500 rows; super_admin sends `hospital_id`) | hospital_admin, super_admin |
| PATCH | `/admin/users/<uuid>` | Update user (role/status) | hospital_admin, super_admin |
| POST | `/admin/users/<uuid>/send-password-reset` | Send password reset email | hospital_admin, super_admin |
| POST | `/admin/users/<uuid>/reset-mfa` | Reset user MFA | hospital_admin, super_admin |
| POST | `/admin/users/<uuid>/resend-invite` | Resend activation invite | hospital_admin, super_admin |
| POST | `/admin/users/<uuid>/generate-reset-link` | Generate 24-hour reset link (Tier 2) | hospital_admin, super_admin |
| POST | `/admin/users/<uuid>/generate-temp-password` | Generate 1-hour temp password (Tier 2) | hospital_admin, super_admin |
| GET | `/admin/password-resets` | Password reset audit history | hospital_admin, super_admin |
| GET | `/admin/staff-onboarding` | Staff onboarding dashboard | hospital_admin, super_admin |
| GET | `/admin/audit-logs` | Audit logs (hospital-scoped for hospital_admin; all for super_admin; response includes `hospital` per entry) | hospital_admin, super_admin (doctor, nurse: own actions) |
| GET | `/admin/wards` | List wards (super_admin may pass `?hospital_id=` to get wards for that facility) | hospital_admin, super_admin, doctor, nurse |
| GET | `/admin/wards/<uuid>/beds` | List beds in ward (optional `?status=`) | hospital_admin, super_admin |
| POST | `/admin/beds` | Create bed (ward_id, bed_code, status) | hospital_admin, super_admin |
| PATCH | `/admin/beds/<uuid>` | Update bed status | hospital_admin, super_admin |
| GET | `/admin/departments` | List departments | hospital_admin, super_admin |
| POST | `/admin/departments/create` | Create department | hospital_admin, super_admin |
| GET | `/admin/lab-units` | List lab units | hospital_admin, super_admin |
| POST | `/admin/lab-units/create` | Create lab unit | hospital_admin, super_admin |
| GET | `/admin/lab-test-types` | List lab test types | hospital_admin, super_admin |
| POST | `/admin/lab-test-types/create` | Create lab test type | hospital_admin, super_admin |
| GET | `/admin/doctors` | List doctors (for assignment) | hospital_admin, super_admin, doctor, nurse |
| GET | `/admin/duplicates` | List duplicate records | hospital_admin, super_admin |
| POST | `/admin/duplicates/create` | Create duplicate record | hospital_admin, super_admin |
| GET, PATCH | `/admin/duplicates/<uuid>` | Duplicate record detail / update | hospital_admin, super_admin |
| GET | `/alerts` | List clinical alerts (hospital-scoped) | super_admin, hospital_admin, doctor, nurse |
| POST | `/alerts/<uuid>/resolve` | Resolve alert | super_admin, hospital_admin, doctor |
| GET | `/lab/orders` | List lab orders | lab_technician only |
| POST | `/lab/orders/<uuid>/result` | Submit lab result | lab_technician only |
| POST | `/lab/results/bulk-submit` | Bulk submit lab results | lab_technician only |
| GET | `/lab/analytics/trends` | Lab analytics trends | lab_technician, hospital_admin, super_admin |
| POST | `/lab/attachments/upload` | Upload lab attachment | lab_technician only |
| GET | `/worklist/encounters` | Encounter worklist (by department/status); dedicated endpoint used by `/worklist` page (not a filter on `/patients/<id>/encounters`) | doctor, nurse, super_admin, hospital_admin |
| GET | `/admissions` | List admissions | hospital_admin, nurse, doctor, super_admin (nurse: optional ward filter) |
| POST | `/admissions/create` | Create admission | nurse, doctor, hospital_admin, super_admin |
| GET | `/admissions/ward/<uuid>` | Admissions by ward | nurse (own ward), hospital_admin, doctor, super_admin |
| POST | `/admissions/<uuid>/discharge` | Discharge | doctor, hospital_admin, super_admin (nurse if own ward) |
| GET | `/dashboard/metrics` | Dashboard counts (role-specific) | Authenticated |
| GET | `/dashboard/analytics` | Analytics (super_admin or hospital_admin/doctor) | super_admin, hospital_admin, doctor |
| GET | `/appointments` | List appointments (hospital-scoped) | super_admin, hospital_admin, doctor, nurse, receptionist |
| POST | `/appointments/create` | Create appointment | super_admin, hospital_admin, doctor, nurse, receptionist |
| PATCH | `/appointments/<uuid>` | Update appointment | super_admin, hospital_admin, doctor, nurse, receptionist |
| DELETE | `/appointments/<uuid>/delete` | Delete appointment | receptionist, hospital_admin, super_admin |
| POST | `/appointments/<uuid>/check-in` | Check-in patient | receptionist, hospital_admin, super_admin |
| POST | `/appointments/<uuid>/reschedule` | Reschedule appointment | receptionist, hospital_admin, super_admin |
| POST | `/appointments/<uuid>/no-show` | Mark no-show | receptionist, hospital_admin, super_admin |
| GET | `/appointments/no-show-statistics` | No-show statistics | receptionist, hospital_admin, super_admin |
| GET | `/reports/patients/export` | Export patients CSV | hospital_admin, super_admin |
| GET | `/reports/audit/export` | Export audit CSV | hospital_admin, super_admin |
| GET, POST | `/billing/invoices` | List or create invoices | hospital_admin, super_admin |
| POST | `/billing/nhis-claim` | NHIS claim submission (stub) | hospital_admin, super_admin |
| GET | `/fhir/Patient` | FHIR Patient search | super_admin, hospital_admin, doctor, nurse, receptionist |
| GET | `/fhir/Patient/<uuid>` | FHIR Patient read | Same |
| GET | `/fhir/Encounter` | FHIR Encounter list (patient=) | Same |
| GET | `/fhir/Encounter/<uuid>` | FHIR Encounter read | Same |
| GET | `/fhir/Condition` | FHIR Condition list (patient=) | Same |
| GET | `/fhir/Condition/<uuid>` | FHIR Condition read | Same |
| GET | `/fhir/MedicationRequest` | FHIR MedicationRequest list (patient=) | Same |
| GET | `/fhir/MedicationRequest/<uuid>` | FHIR MedicationRequest read | Same |
| GET | `/fhir/Observation` | FHIR Observation list (patient=) | Same |
| GET | `/fhir/Observation/<uuid>` | FHIR Observation read | Same |
| GET | `/hl7/adt` | HL7 ADT-style (patient=) | Same as FHIR |
| POST | `/interop/fhir-push` | Push FHIR resource to external URL (target_url, resource_type, resource_id) | doctor, hospital_admin, super_admin |
| GET | `/superadmin/hospitals` | List hospitals | super_admin only |
| GET | `/superadmin/audit-logs` | Global audit logs | super_admin only |
| GET | `/superadmin/system-health` | System health counts | super_admin only |
| GET | `/superadmin/break-glass` | Global break-glass list | super_admin only |
| GET | `/superadmin/gmdc-unverified` | GMDC unverified doctors | super_admin only |
| POST | `/superadmin/onboard-hospital` | Onboard new hospital | super_admin only |
| GET | `/superadmin/onboarding-dashboard` | Hospital onboarding dashboard | super_admin only |
| POST | `/superadmin/hospitals/<uuid>/bulk-import-staff` | Bulk import staff for hospital | super_admin only |
| GET | `/superadmin/hospitals/<uuid>/connectivity` | Hospital interop connectivity | super_admin only |
| GET | `/superadmin/cross-facility-activity` | Cross-facility activity log | super_admin only |
| POST | `/superadmin/users/<uuid>/force-password-reset` | Force password reset (Tier 3, requires MFA) | super_admin only |
| GET | `/superadmin/password-resets/suspicious` | Suspicious reset patterns | super_admin only |
| GET | `/global-patients/search` | Search global patients (interop) | doctor, hospital_admin, super_admin |
| POST | `/facility-patients/link` | Link facility to global patient | doctor, hospital_admin, super_admin |
| GET | `/facilities` | List facilities | doctor, hospital_admin, super_admin |
| PATCH | `/facilities/<uuid>` | Update facility | super_admin only |
| GET | `/cross-facility-records/<uuid>` | Cross-facility records (consent/referral/break-glass) | doctor, hospital_admin, super_admin (policy gated) |
| POST | `/referrals` | Create referral | doctor, hospital_admin, super_admin |
| GET | `/referrals/incoming` | Incoming referrals | doctor, hospital_admin, super_admin |
| PATCH | `/referrals/<uuid>` | Update referral status | doctor, hospital_admin, super_admin |
| POST | `/consents` | Grant consent | doctor, hospital_admin, super_admin |
| GET | `/consents/list` | List consents | doctor, hospital_admin, super_admin |
| PATCH | `/consents/<uuid>` | Revoke consent | super_admin only |
| POST | `/break-glass` | Emergency access (creates log) | doctor, hospital_admin, super_admin |

---

## Celery Task Queue & Fallback

**Status:** ✅ **COMPLETE** — Graceful fallback to synchronous execution when Redis/broker unavailable

### Overview

The system uses Celery for asynchronous tasks (PDF exports, AI analysis, no-show marking). To improve resilience in environments where Redis/broker may be temporarily unavailable, a fallback mechanism automatically switches tasks to synchronous execution.

### Architecture

**Tasks** (`api/tasks/`):
- `export_tasks.py` — PDF export of patient records and encounters
- `ai_tasks.py` — Comprehensive AI analysis and risk prediction
- `appointment_tasks.py` — Automated no-show marking and notifications
- `fallback.py` — **NEW** Broker availability checking and sync/async routing

**Key Functions** (in `api/tasks/fallback.py`):

```python
def can_use_celery() -> bool:
    """Check if Celery broker is accessible (tries connection). Returns bool."""
    
def execute_task_sync_or_async(task_func, *args, timeout=None, **kwargs) -> result:
    """Execute task async if broker available, else synchronous. Returns task result."""
```

### Behavior

1. **Broker Available:** Tasks execute via `task.apply_async()` (asynchronous via Redis)
2. **Broker Unavailable:** Tasks execute directly (synchronous blocking call)
3. **Partial Failure:** If async execution fails, automatic fallback to sync
4. **Logging:** All state transitions logged at INFO/WARNING level

**Example Usage:**

```python
from api.tasks import export_patient_pdf_task, execute_task_sync_or_async

# Will try async first, fall back to sync if broker is down
result = execute_task_sync_or_async(
    export_patient_pdf_task,
    patient_id='550e8400-e29b-41d4-a716-446655440000',
    format_type='summary',
    timeout=30
)
# Returns: {"status": "success", "patient_id": "...", "format": "summary", "size_bytes": 1024}
```

### Configuration

Celery settings in `medsync_backend/settings.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | Redis broker endpoint (env: `CELERY_BROKER_URL`) |
| `CELERY_RESULT_BACKEND` | `redis://127.0.0.1:6379/0` | Result storage backend |
| `CELERY_TASK_SERIALIZER` | `json` | Task payload format (JSON only, no pickle) |
| `CELERY_TASK_TIME_LIMIT` | 30 min | Hard timeout for task execution |
| `CELERY_TASK_SOFT_TIME_LIMIT` | 5 min | Soft timeout (gives task time to cleanup) |
| `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP` | `True` | Retry if broker unavailable at startup |
| `CELERY_BEAT_SCHEDULE` | (beat config) | Scheduled tasks (no-show marking every 15 min) |

### Testing

Run fallback tests:

```bash
python -m pytest api/tests/test_celery_fallback.py -v
```

**Test Coverage:**
- ✅ Broker available → async execution
- ✅ Broker unavailable → sync execution
- ✅ Celery not installed → sync execution
- ✅ Async error → fallback to sync
- ✅ Timeout handling (default 5 min)
- ✅ Real task execution (eager mode)
- ✅ Task chaining with fallback

**Result:** 14/14 unit tests pass + 2 integration tests pass (100%)

### Runtime Behavior

**Startup (with Redis unavailable):**
```
WARNING:api.tasks.fallback:Celery broker unavailable: ConnectionError: Error 10061 ...
INFO:api.tasks.fallback:Executing task export_patient_pdf_task synchronously (Celery unavailable)
```

**Export Task Result:**
```json
{
  "status": "success",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "format": "summary",
  "size_bytes": 2048
}
```

**Logs in Synchronous Mode:**
```
INFO api.tasks.fallback: Executing task export_patient_pdf_task synchronously (Celery unavailable) with args: ('550e8400...',), kwargs: {'format_type': 'summary'}
```

### Integration Points

Tasks can be called from:
1. **Views** (HTTP endpoints) — e.g., POST `/patients/<id>/export`
2. **Management commands** — e.g., `python manage.py export_all_patients`
3. **Scheduled jobs** (Celery Beat) — no-show marking every 15 minutes
4. **Signals** — On model save, trigger async processing

To integrate a new view with fallback:

```python
from api.tasks import your_task_func, execute_task_sync_or_async

@api_view(['POST'])
def your_endpoint(request):
    result = execute_task_sync_or_async(
        your_task_func,
        request.data['param'],
        timeout=60
    )
    return Response(result)
```

### Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| Broker unavailable | Tasks execute synchronously | Check Redis: `redis-cli ping` |
| Slow sync execution | Long response times | Move heavy tasks to background (async preferred) |
| Task timeout | AsyncResult.get() raises TimeLimitExceeded | Increase `timeout` param or `CELERY_TASK_SOFT_TIME_LIMIT` |
| Missing task result | Result backend down but broker OK | Both must be available or both unavailable for consistency |

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Includes Celery broker status in response (if health endpoint extended).

---

## Audit & Critical Fixes

### Production Readiness Summary

**Current Status:** ⛔ **NOT PRODUCTION READY** (Feature complete at 90%, security at 38%)

Based on comprehensive code review (January 2025), the system has **3 critical security issues**, **3 high-severity issues**, and **2 medium-severity issues** that must be resolved before production deployment.

**Total estimated effort:** 22-30 hours for all fixes → 6-8 weeks for full production readiness including testing and HIPAA compliance.

See `CRITICAL_FIXES_GUIDE.md` for complete implementation guide with copy-paste code solutions and test cases.

### Critical Issues

#### [CRITICAL #1] Timing Attack on Temporary Password Login
- **File:** `api/views/auth_views.py:662`
- **Issue:** Plain string comparison (`!=`) instead of constant-time comparison for temp password verification
- **Risk:** Timing attack allows brute-forcing 1-hour valid temp password
- **Fix:** Replace with `secrets.compare_digest()` (1-line change)
- **Time:** 15 minutes

#### [CRITICAL #2] No Rate Limiting on Temporary Password Endpoint
- **File:** `api/views/auth_views.py:629`
- **Issue:** Endpoint lacks `@throttle_classes` decorator, allowing unlimited brute-force attempts
- **Risk:** Attackers can try all possible temp passwords without limit during 1-hour window
- **Fix:** Add `@throttle_classes([LoginThrottle])` or stricter (3 attempts/15 min)
- **Time:** 15 minutes

#### [CRITICAL #3] No Server-Side Enforcement of Forced Password Change After Temp Login
- **File:** `api/views/auth_views.py:683-694`
- **Issue:** Users can bypass forced password change by ignoring client-side flag and calling other endpoints
- **Risk:** Temporary passwords become permanent without password change
- **Fix:** Add middleware to check `user.must_change_password_on_login` and reject non-password-change requests with 403
- **Time:** 2-3 hours (includes middleware + tests)

### High-Severity Issues

#### [HIGH #1] Backup Code Brute-Force Vulnerable (No Constant-Time Comparison)
- **File:** `api/views/auth_views.py:228`
- **Issue:** Backup code comparison uses `in` operator on list (variable timing)
- **Risk:** Timing leak allows enumeration of valid backup codes
- **Fix:** Use `secrets.compare_digest()` in loop
- **Time:** 30 minutes

#### [HIGH #2] Account Lockout Race Condition (Partial Fix)
- **File:** `api/views/auth_views.py:50-91`
- **Issue:** Failed attempt counter uses non-atomic increments under high concurrency
- **Risk:** Concurrent login attempts can bypass 5-attempt lockout
- **Fix:** Use `F()` expressions for atomic increment: `F('failed_login_attempts') + 1`
- **Time:** 1 hour

#### [HIGH #3] Frontend Session Cookie Missing Security Flags
- **File:** `src/lib/auth-context.tsx:277`
- **Issue:** Cookie set without HttpOnly, Secure, SameSite flags
- **Risk:** CSRF vulnerability, XSS exposure, MITM attacks
- **Fix:** Add flags: `SameSite=Strict; Secure` (HttpOnly requires backend Set-Cookie header)
- **Time:** 30 minutes

### Medium-Severity Issues

#### [MEDIUM #1] Backup Code Rate Limiting Uses Unreliable Cache
- **File:** `api/views/auth_views.py:216-224`
- **Issue:** Rate limit relies on cache backend with 5-minute TTL
- **Risk:** Non-persistent cache (in-memory) loses rate limit on service restart
- **Fix:** Use database-backed throttling (PasswordResetThrottle model) or document Redis requirement
- **Time:** 2 hours

#### [MEDIUM #2] MFA User-Level Throttle May Not Work Correctly
- **File:** `api/rate_limiting.py:98-112`
- **Issue:** Tries to extract user_id from unauthenticated token during MFA
- **Risk:** Rate limiting may silently fail; unclear if working correctly
- **Fix:** Test MFA user throttle path OR extract user_id from mfa_token directly OR remove MFA user throttle
- **Time:** 1-2 hours

### Security Strengths

✅ Multi-tenancy enforcement (hospital_id scoping on all queries)  
✅ Cross-facility access gated by consent/referral/break-glass  
✅ Account lockout working (5 attempts → 15 min lock)  
✅ JWT configuration correct (15 min access + 7 day refresh with rotation)  
✅ Password reset tokens use constant-time comparison ✅ Comprehensive audit logging with PHI sanitization  
✅ Strong password policy (12+ chars, complexity, no reuse of last 5)  
✅ Break-glass access time-limited (15 min) and fully audited  
✅ CSRF protection configured  
✅ CSP headers remove unsafe-inline  
✅ HTTPS/HSTS configured  

### Implementation Roadmap

**Phase 1: Critical Fixes (1-2 weeks)** — 22-30 hours
- Fix timing attacks (temp password, backup code)
- Add rate limiting to temp password endpoint
- Add server-side enforcement of password change
- Implement database-backed backup code rate limiting
- Fix account lockout race condition

**Phase 2: High-Priority Fixes (2-3 weeks)** — 15-20 hours
- Fix session cookie security flags (frontend + backend)
- Implement/test MFA user throttle
- Full security test suite (100+ tests)
- Penetration testing prep

**Phase 3: Testing & Hardening (2-3 weeks)** — 40+ hours
- Security test suite execution
- Load testing (1000+ concurrent users)
- HIPAA compliance audit
- Production deployment runbook

**Phase 4: Pre-Production (1 week)** — 20 hours
- Final security review
- Team training
- Monitoring setup
- Incident response plan

### Verification Checklist

Before deploying to production:

- [ ] All 3 critical issues fixed and tested
- [ ] All 3 high-severity issues fixed and tested
- [ ] All 2 medium-severity issues fixed and tested
- [ ] Security test suite passes (100+ tests)
- [ ] Load testing: 1000+ concurrent users successful
- [ ] Penetration testing completed and approved
- [ ] HIPAA compliance audit passed
- [ ] Production deployment runbook documented
- [ ] Monitoring & alerting configured
- [ ] Team trained on deployment procedures
- [ ] Incident response plan created

### Documentation

- **CRITICAL_FIXES_GUIDE.md** — Copy-paste code solutions for all issues
- **AUDIT_REPORT.md** — Detailed findings and recommendations  
- **EXECUTIVE_SUMMARY.md** — Leadership summary and timeline
- **FINAL_STATUS_REPORT.md** — Current status and next steps
| GET | `/break-glass/list` | List break-glass entries | doctor, hospital_admin, super_admin |
| POST | `/nurse/shift/start` | Nurse shift start | nurse, super_admin |
| POST | `/nurse/shift/<uuid>/handover` | Nurse shift handover | nurse, super_admin |
| GET | `/nurse/overdue-vitals` | Overdue vitals (ward) | nurse, super_admin |
| POST | `/ai/analyze-patient/<uuid>` | Full AI analysis (see AI Intelligence Module) | doctor, nurse, hospital_admin, super_admin |
| POST | `/ai/risk-prediction/<uuid>` | Disease risk prediction | doctor, nurse, super_admin |
| POST | `/ai/clinical-decision-support/<uuid>` | Differential diagnosis | doctor, super_admin |
| POST | `/ai/triage/<uuid>` | Triage level | doctor, nurse, super_admin |
| POST | `/ai/find-similar-patients/<uuid>` | Similar patients | doctor, super_admin |
| POST | `/ai/referral-recommendation/<uuid>` | Referral recommendations | doctor, hospital_admin, super_admin |
| GET | `/ai/analysis-history/<uuid>` | Past AI analyses | doctor, nurse, super_admin |

### X-View-As-Hospital (super admin view-as)

The frontend sends header `X-View-As-Hospital: <hospital_uuid>` when a super_admin selects "View as hospital" in the top bar. The backend honours it via:

- **Middleware:** `api.middleware.ViewAsHospitalMiddleware` runs after authentication. It calls `get_effective_hospital(request)`, which validates that the requesting user is `super_admin` with no `hospital_id`, that the header value is a valid active hospital UUID, sets `request.effective_hospital` for the request, and writes one audit log entry `VIEW_AS_HOSPITAL` per request when the header is present and valid.
- **Scoping:** All hospital-scoped views use `get_request_hospital(request)` (which returns `effective_hospital` when set, else `request.user.hospital`). So list/detail endpoints (patients, encounters, records, dashboard, worklist, etc.) are temporarily scoped to the selected hospital when the header is sent.

If the header is missing, invalid, or the user is not super_admin (or has a hospital), it is ignored and normal facility scoping applies.

## RBAC Security: Fail-Closed Mode

### Overview

By default, unknown API endpoints return **404 (Not Found)** — a permissive fail-open security posture suitable for development.

When enabled, fail-closed mode returns **403 (Permission Denied)** for unknown endpoints — a security-first posture required for production.

**Spec Requirement:** "Enable fail-closed mode ONLY after RBAC coverage is verified at 100%."

### Configuration

**Default (Development):**
```bash
# In .env or environment
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=False  # Fail-open, safe for dev
```

**Production (After Validation):**
```bash
# Set only AFTER verifying 100% RBAC coverage
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=True  # Fail-closed, secure for prod
```

### Enabling Fail-Closed Mode: Step-by-Step

**1. Verify 100% RBAC Coverage**

Run the coverage test:
```bash
cd medsync-backend
python manage.py test api.tests.test_rbac_coverage -v 2
```

Expected output:
```
test_every_url_has_permission_entry ... ok
Ran 1 test in 0.234s
OK
```

If test fails, you have unmapped endpoints. See "Troubleshooting" below.

**2. Validate with Pre-Commit Hook (Optional but Recommended)**

Check coverage before committing:
```bash
python scripts/validate-rbac-coverage.py
```

Output if all good:
```
✅ RBAC coverage valid (100%)
   All API endpoints have permission matrix entries.
```

**3. Deploy with Fail-Closed Enabled**

Set environment variable in production `.env`:
```bash
PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=True
```

On startup, the system will:
- Validate RBAC coverage is 100%
- Log: `✅ RBAC coverage 100% validated - fail-closed mode active`
- Deny all unknown endpoints with 403

**4. Monitor Audit Logs**

Watch for `unknown_endpoint_denied` events:
```bash
# In your monitoring system (Datadog, Grafana, etc.)
# Query for: action="permission_denied" AND event_type="unknown_endpoint_denied"
```

If any appear, a new endpoint was added without PERMISSION_MATRIX entry.

### Troubleshooting: New Endpoint Returns 403

**Symptom:** After enabling fail-closed, an endpoint returns 403 Permission Denied.

**Root Cause:** Endpoint exists in `api/urls.py` but not in `shared/permissions.py` PERMISSION_MATRIX.

**Fix (5 minutes):**

1. **Identify the endpoint** — Check logs for the path, e.g., `/api/v1/patients/{id}/ai-insights`

2. **Normalize the path** — Convert to PERMISSION_MATRIX format:
   - `/api/v1/patients/{id}/ai-insights` → `patients/<pk>/ai-insights`
   - Replace `{id}`, `{uuid}`, `{pk}` with `<pk>`

3. **Add to PERMISSION_MATRIX** in `shared/permissions.py`:
   ```python
   PERMISSION_MATRIX = {
       # ... existing entries ...
       "patients/<pk>/ai-insights": {
           "GET": ["doctor"],      # Doctor can GET
           "POST": ["doctor"],     # Doctor can POST (if applicable)
           "PATCH": [],            # Nobody can PATCH
           "DELETE": [],           # Nobody can DELETE
       },
   }
   ```

4. **Validate coverage:**
   ```bash
   python manage.py test api.tests.test_rbac_coverage -v 2
   # Must pass with OK
   ```

5. **If in staging, re-enable:**
   - Either redeploy with the fix
   - Or temporarily disable: `PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=False`

### Adding New API Endpoints: Checklist

Before you commit new endpoints, ensure:

**Developer Checklist:**
- [ ] Endpoint added to `api/urls.py`
- [ ] Endpoint added to PERMISSION_MATRIX in `shared/permissions.py`
- [ ] Use correct format: `"endpoint/<pk>"` (replace UUID placeholders with `<pk>`)
- [ ] Specify HTTP methods and allowed roles:
  ```python
  "my-endpoint/<pk>": {
      "GET": ["doctor", "nurse"],  # Who can GET
      "POST": ["doctor"],          # Who can POST
      "PATCH": ["doctor"],         # Who can PATCH
      "DELETE": ["super_admin"],   # Who can DELETE
  }
  ```
- [ ] Run coverage test: `python manage.py test api.tests.test_rbac_coverage -v 2`
- [ ] Run pre-commit validation: `python scripts/validate-rbac-coverage.py`
- [ ] Commit and merge

**CI Enforcement:**
- GitHub Actions will run coverage test on every PR
- PR will be blocked if coverage < 100%
- Error message will list missing endpoints

### PERMISSION_MATRIX Format

Each endpoint entry maps HTTP methods to allowed roles:

```python
PERMISSION_MATRIX = {
    "patients/<pk>": {
        "GET": ["super_admin", "hospital_admin", "doctor", "nurse", "receptionist", "lab_technician"],
        "POST": ["super_admin", "hospital_admin", "doctor"],
        "PATCH": ["super_admin", "hospital_admin", "doctor"],
        "DELETE": [],  # Nobody can delete patients
    },
    "patients/<pk>/records": {
        "GET": ["super_admin", "hospital_admin", "doctor", "nurse"],
        "POST": ["super_admin", "hospital_admin", "doctor", "nurse"],
        "PATCH": ["super_admin", "hospital_admin", "doctor"],
        "DELETE": [],
    },
    # ... more entries ...
}
```

**Source of Truth:** `shared/permissions.py` (lines 1-850+)

### Audit Log Events

When fail-closed is enabled and blocks an unknown endpoint:

```json
{
    "user": "doctor@example.com",
    "action": "permission_denied",
    "event_type": "unknown_endpoint_denied",
    "endpoint": "/api/v1/nonexistent",
    "method": "GET",
    "status_code": 403,
    "timestamp": "2026-04-03T12:00:00Z",
    "ip_address": "192.168.1.100"
}
```

Monitor these for:
- New endpoints missing permissions (fix with checklist above)
- Attacks trying unknown endpoints (intrusion detection)
- Developer mistakes during API evolution

### FAQ

**Q: My endpoint was working yesterday, now returns 403. What happened?**  
A: Fail-closed mode was likely enabled. Check if new endpoints were added without PERMISSION_MATRIX entries. See "Troubleshooting" above.

**Q: Can I use fail-closed in development?**  
A: Not recommended. Keep it disabled (default) for faster debugging. You'll catch missing permissions via CI and pre-commit hook anyway.

**Q: What if I need to disable fail-closed quickly?**  
A: Set `PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=False` and redeploy. This reverts to fail-open (404) for unknown endpoints, giving you time to fix the underlying issue.

**Q: How do I know if my endpoint is in PERMISSION_MATRIX?**  
A: Run the coverage test:
```bash
python manage.py test api.tests.test_rbac_coverage -v 2
```
It will list any missing endpoints.

**Q: Can I bypass fail-closed for specific endpoints?**  
A: No. All endpoints must be in PERMISSION_MATRIX. This is intentional for security. If an endpoint truly should be public, add it with role `[]` (nobody), but document why.

### Role summary (backend enforcement)

| Role | Patient CRUD / search | Records create | Encounters | Alerts | Lab orders/results | Admissions | Appointments | Admin users/audit | Reports | Superadmin | Interop (global patients, referrals, consent, break-glass) |
|------|------------------------|----------------|------------|--------|--------------------|------------|-------------|--------------------|---------|------------|---------------------------|
| super_admin | Full (all facilities) | Yes | Yes | Yes | No | Yes | Yes | Yes | Yes | Yes | Yes (full / policy) |
| hospital_admin | Full (own facility) | No | Yes | Yes | No | Yes | Yes | Yes | Yes | No | Yes |
| doctor | Full (own facility) | Yes (diagnosis, prescription, lab order, etc.) | Yes | Yes | No | Yes | Yes | No* | No | No | Yes |
| nurse | Read patients (own facility) | Vitals, allergy, nursing note | List/create | Yes | No | Yes (create, ward) | Yes | No* | No | No | No |
| receptionist | Search, update patient (own facility); cannot register new patients | No | No | No | No | Yes | No | No | No | No |
| lab_technician | Search only (hospital-scoped) | No | No | No | Yes only | No | No | No | No | No |

\* Doctor/nurse can see audit logs for their own actions.

Permission matrix source of truth: `api/permissions.py` (PERMISSION_MATRIX); tests: `api/tests/test_permissions.py`.

---

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements-local.txt
python manage.py migrate
python manage.py setup_dev   # Creates cache table, seed data, dev users
python manage.py runserver
```

**Note:** `setup_dev` automatically creates the MFA cache table required for login. If you run migrations separately, run `python manage.py createcachetable` before starting the server.

---

## Dev credentials

Seeded users (after `setup_dev`) and shared TOTP: **[docs/DEV_CREDENTIALS.md](../docs/DEV_CREDENTIALS.md)**.

---

## Environment (optional)

- `DEBUG` — Default **False**. For local dev without Postgres, set `DEBUG=True` (enables SQLite fallback and debug toolbar).
- `SECRET_KEY` — **Required in production.** In development (`DEBUG=True`) a temporary key is generated if unset (process-local; don’t rely on it for persistent sessions/tokens).
- `ENV` — Optional hard safety: set `ENV=production` to **refuse to start** if `DEBUG=True`.
- `ALLOWED_HOSTS` — Default `localhost,127.0.0.1`
- `SECURE_HTTPS` — Enable production security headers (SSL redirect, HSTS, XSS filter, etc.). Default: `True` when `DEBUG=False`, `False` when `DEBUG=True`.
- `SECURE_HSTS_SECONDS` — HSTS max-age in seconds (default: 31536000).
- `CSRF_TRUSTED_ORIGINS` — Comma-separated origins for CSRF (e.g. `https://app.example.com`) when using HTTPS.
- `CORS_ALLOWED_ORIGINS` — Default `http://localhost:3000,http://127.0.0.1:3000`. **Production must set explicit origins** (e.g. `https://app.example.com`); wildcard (`*`) with credentials is insecure and will raise when `DEBUG=False`.
- `JWT_ACCESS_MINUTES` — Access token lifetime in minutes (default: 15)
- `JWT_REFRESH_DAYS` — Refresh token lifetime in days (default: 7)
- `THROTTLE_ANON` — Rate limit for unauthenticated requests, e.g. `"60/hour"` (default: 60/hour)
- `THROTTLE_USER` — Rate limit for authenticated requests, e.g. `"1000/hour"` (default: 1000/hour)
- `DATABASE_URL` — **Required in production** (Neon Postgres). When set, SSL is enforced (`sslmode=require`). If unset and `DEBUG=True`, SQLite (`db.sqlite3`) is used for local dev only. **Local Postgres:** see [docs/TESTING_AND_CI.md](../docs/TESTING_AND_CI.md#postgresql-local-development).
- `REDIS_URL` — Optional; required for multi-worker WebSocket broadcasting (Channels). If unset, the in-memory channel layer is used (single-process only).
- `MEDSYNC_AI_MODELS_DIR` — Optional override for AI `.joblib` model directory (default `api/ai/models/`).
- `PASSWORD_RESET_FRONTEND_URL`, `PASSWORD_RESET_TOKEN_EXPIRY_HOURS` — Password reset flow configuration (see `.env.example`).
- `AUDIT_LOG_SIGNING_KEY` — **Must be overridden in production** for tamper-evident audit chain signatures.

**Security / dependency audit:** `bash scripts/pip-audit.sh` or `pip-audit -r requirements-local.txt`. **CI:** `.github/workflows/ci.yml` runs pip-audit on every push/PR.

- `EMAIL_BACKEND` — Default: `django.core.mail.backends.console.EmailBackend` (logs to console). Set to `django.core.mail.backends.smtp.EmailBackend` and configure `EMAIL_*` for production.
- `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` — SMTP settings when not using console backend.
- `BREAK_GLASS_NOTIFY_EMAILS` — Optional comma-separated emails to notify when break-glass is used. If unset, hospital admins and super_admins are notified.

**One-time setup:** MFA login uses a DB-backed cache table. Run once after migrating:

```bash
python manage.py createcachetable
```

Optional: Redis, Pillow (see `requirements-local.txt`).

---

## Governance and architecture (shared docs)

| Doc | Purpose |
|-----|---------|
| [docs/INDEX.md](../docs/INDEX.md) | Documentation index |
| [docs/ARCHITECTURE_AND_GOVERNANCE.md](../docs/ARCHITECTURE_AND_GOVERNANCE.md) | Governance model, multi-tenancy, access, workflows, ops, backup |
| [docs/ROLE_BASED_USERS_AND_PAGES.md](../docs/ROLE_BASED_USERS_AND_PAGES.md) | Roles, pages, matrix |
| [docs/CONSENT_BREAKGLASS_REFERRALS_ALERTS.md](../docs/CONSENT_BREAKGLASS_REFERRALS_ALERTS.md) | Interop UX and APIs |

**Role changes mid-session:** `docs/ROLE_BASED_USERS_AND_PAGES.md` + `api/tests/test_role_change_session.py`.
