# GitHub Copilot Instructions for MedSync EMR

MedSync is a **centralized, multi-hospital Electronic Medical Records (EMR) system** built for Ghana's inter-hospital network. It provides role-based access, clinical records management, patient admissions, lab orders, referrals, and cross-facility record sharing with consent/break-glass emergency access.

## Repository Structure

- **`medsync-backend/`** — Django 4.2+ REST API with JWT+TOTP/Passkey MFA, multi-tenancy, audit logging, FHIR/HL7 interop. Multi-app layout: `core/`, `patients/`, `records/`, `interop/`, `api/`, `shared/`
- **`medsync-frontend/`** — Next.js (App Router) + React + TypeScript frontend with role-based dashboards, Playwright e2e tests, Sentry integration
- **`docs/`** — Eight-chapter project documentation (chapters 0–7; see Documentation References below)

## Build, Test, and Lint Commands

### Backend (Django/Python)

From `medsync-backend/` directory:

**Setup (first time):**
```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate
pip install -r requirements-local.txt
cp .env.example .env
python manage.py migrate
python manage.py setup_dev  # Load seed data (runs from core app)
python manage.py runserver
```

Dev credentials created by `setup_dev`:
```
admin@medsync.gh / Admin123!@#          (super_admin)
doctor@medsync.gh / Doctor123!          (doctor)
doctor2@medsync.gh / Doctor234!         (doctor)
hospital_admin@medsync.gh / HospitalAdmin123!
nurse@medsync.gh / Nurse123!@#
receptionist@medsync.gh / Receptionist123!@#
lab_technician@medsync.gh / LabTech123!@#
```

**Testing:**
```bash
python -m pytest api/tests/ -v          # Run all tests with verbose output
python -m pytest api/tests/test_auth.py -v  # Single test file
python -m pytest api/tests/ -k "test_password_policy" -v  # By keyword
```

**Database:**
```bash
python manage.py migrate              # Apply migrations
python manage.py makemigrations       # Create new migrations
python manage.py setup_dev            # Reset and seed dev data
python manage.py fix_migration_history  # Fix existing DB migration inconsistencies
```

**Other management commands (located in `core/management/commands/`):**
```bash
python manage.py setup_production     # Production bootstrap
python manage.py enable_mfa           # Enable MFA for a user
python manage.py dev_totp_code        # Print current TOTP code for a dev user
python manage.py dbbackup             # Trigger a DB backup
python manage.py check_rbac_coverage  # Validate RBAC coverage across all views
python manage.py seed_nhis_demo       # Seed NHIS demo patients (requires setup_dev first)
```

**Health check (when running):**
```bash
curl http://localhost:8000/api/v1/health
```

**Config:** Uses `python-decouple` for environment variables (`.env` file). Key vars: `DEBUG`, `DATABASE_URL`, `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `AUDIT_LOG_SIGNING_KEY`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `CORS_ALLOWED_ORIGINS`, `WEBAUTHN_RP_ID`, `WEBAUTHN_ORIGIN`.

### Frontend (Next.js)

From `medsync-frontend/` directory:

**Setup:**
```bash
npm install
cp .env.example .env  # Set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm run dev
```

**Testing:**
```bash
npm run test        # Run all unit tests once
npm run test:watch  # Watch mode
```

**E2E tests (Playwright):**
```bash
npx playwright test          # Run all e2e tests
npx playwright test --ui     # Interactive UI mode
```

**Building & running:**
```bash
npm run build  # Production build
npm run start  # Start production server
npm run lint   # ESLint check
```

**Config:** Environment file sets `NEXT_PUBLIC_API_URL` (public API endpoint). Frontend expects backend at `http://localhost:8000/api/v1` by default.

### Vercel (frontend vs API)

Use **two Vercel projects** linked to the same Git repository:

| Project | Root Directory | Purpose |
|--------|----------------|---------|
| API | `.` (repository root) | Django: root `vercel.json` runs `pip install -r requirements-vercel.txt` and `asgi.py`. |
| UI | `medsync-frontend` | Next.js: install/build run only inside `medsync-frontend/` (`medsync-frontend/vercel.json`). |

If Root Directory is left at `.` for the UI, Vercel applies the **Python** install from the root `vercel.json` and the Next app never builds correctly. In the Vercel dashboard: **Project → Settings → General → Root Directory** → `medsync-frontend`.

### Production Prerequisites (hard blockers before go-live)

These three items are **not configured by default** and will cause silent failures or startup errors in production:

1. **SMTP — email delivery** Email OTP (MFA) and password-reset links are silent no-ops until a real SMTP provider is wired up. Set these env vars (see `.env.example` for Mailtrap, SendGrid, Mailgun, and Gmail examples):
   ```
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=...
   EMAIL_PORT=...
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=...
   EMAIL_HOST_PASSWORD=...
   DEFAULT_FROM_EMAIL=MedSync EMR <noreply@medsync.gh>
   ```

2. **WebAuthn — passkey auth** The passkey MFA method will break if these don't match the deployed domain exactly (no protocol prefix, no trailing slash on RP ID):
   ```
   WEBAUTHN_RP_ID=medsync.gh          # domain only, e.g. medsync.gh
   WEBAUTHN_ORIGIN=https://medsync.gh  # full origin with scheme
   ```

3. **`ADMIN_URL` — non-guessable admin path** The backend **refuses to start** in production if `ADMIN_URL` is left as `admin/`. Generate a safe path and set it:
   ```bash
   python -c "import secrets; print('ms-admin-' + secrets.token_hex(4) + '/')"
   ```
   ```
   ADMIN_URL=ms-admin-<generated>/
   ```

---

## High-Level Architecture

### Multi-Tenancy: Hospital-Scoped Access

**Core principle:** "Every user belongs to a hospital; data is scoped by hospital."

- **User model:** Each user has `role`, `hospital_id`, and optional `ward_id`, `department_link`, `lab_unit`. Hospital assignment is **not chosen by the user** at login—it's fixed on the account.
- **Data ownership:** All clinical data (encounters, admissions, appointments, lab orders) stores `hospital_id`. Non-super_admin users see only their hospital's data.
- **Super Admin:** No hospital assigned; can see all data. Can pass `X-View-As-Hospital` header to audit a specific hospital's scope.
- **Hospital Admin:** Assigned to one hospital; manages that hospital's staff, audit logs, and facility config.

**Key enforcement:** `TenantManager` (centralized in `core/models.py`) and `get_patient_queryset()` filter all queries based on user's hospital and role. `can_access_cross_facility()` gates cross-hospital access and enforces NDPA data-residency rules.

### Cross-Facility Interoperability (HIE Layer)

The system supports shared medical records across hospitals via:

1. **Global Patient Registry** — Unique identifier (GPID) for a patient across all hospitals. `GlobalPatient` records carry `data_residency_country` (ISO 3166-1 alpha-2, default `"GH"`) and a `data_residency_locked` flag for NDPA § 36 transfer restrictions.
2. **Consent** — Hospital A can consent to Hospital B accessing their records; scope is `SUMMARY` (demographics only) or `FULL_RECORD` (includes clinical data).
3. **Referrals** — Doctor at Hospital A can refer a patient to Hospital B; referral status is tracked (pending/accepted/completed/rejected).
4. **Break-Glass Emergency Access** — Any authorized user can access records in an emergency (last 15 minutes, fully logged/audited).

**Data residency:** `Hospital.country` (default `"GH"`) is checked against `GlobalPatient.data_residency_country` when `data_residency_locked=True`; cross-border access is blocked even with consent.

**Access control:** All enforced server-side; API is the authority. Logged in `AuditLog` with action `VIEW`, `CREATE_REFERRAL`, `EMERGENCY_ACCESS`, etc.

### Authentication & Security

- **JWT + MFA:** Simple JWT for access/refresh tokens. Three MFA methods: `email` (email OTP), `totp` (authenticator app via django-otp/pyotp), `passkey` (WebAuthn/FIDO2 via `use-passkey.ts` on the frontend; `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` env vars required).
- **Access token TTL:** 15 minutes (configurable via `JWT_ACCESS_MINUTES`); refresh token 7 days.
- **Token blacklist:** On logout or refresh rotation, tokens are blacklisted server-side (Simple JWT blacklist).
- **Adaptive MFA / TrustedDevice:** After a successful MFA ceremony, a `TrustedDevice` record (SHA256 fingerprint) is created with a 30-day sliding expiry. On subsequent logins from the same device the step-up challenge is skipped (risk_tier=1). Users can revoke devices; Hospital IP subnets (`Hospital.ip_subnets`) can further reduce MFA friction on trusted networks.
- **Password policy:** 12+ chars, uppercase, lowercase, digit, symbol; no reuse of last 5 passwords (enforced via `api.password_policy.validate_password()` and `UserPasswordHistory` model).
- **3-tier password recovery:** (1) Self-service email reset link, (2) temporary password set by Hospital Admin, (3) account unlock by Super Admin. Fields on `User`: `password_reset_token`, `temp_password`, `must_change_password_on_login`.
- **Field-level encryption:** PHI columns (patient demographics, vitals, clinical notes, diagnoses) encrypted at rest using `django-cryptography` (AES-256 via Fernet). Requires `FIELD_ENCRYPTION_KEY` env var.
- **Audit log integrity:** Tamper-evident hash-chain on `AuditLog`; each entry signs the previous chain hash via HMAC. Requires `AUDIT_LOG_SIGNING_KEY` env var.

**Token storage:** Tokens stored in **sessionStorage only** (cleared on tab close). The "remember me" / localStorage flow has been removed for security. Super Admin's view-as selection is persisted in sessionStorage per tab.

### Backend App Layout

The backend is split across six Django apps:

| App | Models |
|-----|--------|
| `core` | `Hospital`, `Ward`, `Bed`, `Department`, `LabUnit`, `User`, `TrustedDevice`, `UserPasskey`, `MFASession`, `AuditLog` |
| `patients` | `Patient`, `PatientAdmission` |
| `records` | `Encounter`, `MedicalRecord`, `Diagnosis`, `Prescription`, `Vital`, `LabOrder`, `LabResult`, `NursingNote` |
| `interop` | `GlobalPatient`, `FacilityPatient`, `Consent`, `Referral`, `BreakGlassLog` |
| `api` | `ClinicalRule`, `CdsAlert`, `DrugStock`, `Dispensation`, `StockMovement`, `StockAlert` (CDS + pharmacy); all views, serializers, permissions |
| `shared` | Shared utilities and app config |

Views in `api/views/` are organized by feature: `patient_views.py`, `record_views.py`, `admin_views.py`, `consent_views.py`, `referral_views.py`, `billing_views.py`, `pharmacy_views.py`, `pharmacy_stock_views.py`, `cds_views.py`, `shift_views.py`, `mar_views.py`, `alert_views.py`, `break_glass_views.py`, `superadmin_views.py`, `fhir_views.py`, `hl7_views.py`, etc.

### Database

- **Development:** SQLite (auto-used when `DEBUG=True` and `DATABASE_URL` unset).
- **Production:** PostgreSQL via Neon (connection string set in `DATABASE_URL` env var; backend uses `dj-database-url` and forces `sslmode=require`).
- **Runtime:** WSGI only (Gunicorn). Channels/WebSocket has been removed.

**Migrations:** Each Django app has a squash migration (`0001_squashed_*`) that creates tables in their final encrypted form. Subsequent numbered migrations (e.g. `0015_*`, `0022_*`) add new fields or models. All PHI fields are created encrypted from the start in squash migrations — never plain-then-altered.

---

## Key Conventions

### Backend (Django/DRF)

1. **Facility scoping:** Use `get_effective_hospital(request)` to get the hospital context; returns `user.hospital` for non-super_admin, None for super_admin with no hospital.

2. **View structure:** Views in `api/views/` organized by feature. Most return 403 if user role is not authorized (see `_block_non_clinical_roles()` for examples). RBAC coverage is checked at startup when `_RBAC_COVERAGE_WARNING_ENABLED=True`.

3. **Audit logging:** Call `AuditLog.log_action()` after create/update/delete operations. Always sanitize `resource_id` via `sanitize_audit_resource_id()` to avoid logging PHI or tokens.

4. **Serializers:** In `api/serializers.py`, all use DRF's standard patterns. Clinical record create endpoints enforce `patient.registered_at.id == user.hospital.id`.

5. **Password policy:** Import `api.password_policy.validate_password()` and `check_password_reuse()` for account activation and password reset. Use `UserPasswordHistory` to track last 5 hashes.

6. **FHIR/HL7:** Read-only endpoints in `api/views/fhir_views.py` and `api/views/hl7_views.py`. Map internal models (Patient, Encounter, Diagnosis, Prescription, Vital) to FHIR resources.

7. **Error codes:** Return 400 for validation, 403 for permission, 404 for not found, 503 for DB down (health endpoint).

8. **Hospital model extras:** `Hospital.facility_type` encodes the Ghana referral hierarchy (CHPS → Health Centre → District → Regional → Teaching). `Hospital.is_archived` / `Hospital.archive()` support soft-delete without destroying patient data.

### Frontend (Next.js/React)

1. **File structure** (all source under `src/`):
   - `src/app/` — Pages (auth routes in `(auth)/`, authenticated app in `(dashboard)/`)
   - `src/components/` — Organized by `layout/` (Sidebar, TopBar), `features/` (domain-specific), `ui/` (reusable)
   - `src/hooks/` — API integration (one per feature: `use-patients.ts`, `use-admin.ts`, `use-pharmacy.ts`, `use-nurse.ts`, `use-lab.ts`, `use-passkey.ts`, `use-shift-handover.ts`, `use-cds-alerts.ts`, `use-fhir-export.ts`, etc.)
   - `src/lib/` — Utilities (`api-client.ts`, `auth-context.tsx`, `types.ts`, `navigation.ts`, `permissions.ts`, `i18n/`, password validation, passkey)
   - `e2e/` — Playwright end-to-end tests (roles/, scenarios/, security/, workflows/)

2. **API client:** `src/lib/api-client.ts` provides `createApiClient()` with `getToken()`, `setToken()`, `onRefresh()` for token management. Uses `fetch` with headers, retries on 401 with refresh.

3. **Role-based UI:**
   - Import `useAuth()` (from `src/lib/auth-context.tsx`) to get `user.role` and `user.hospital`.
   - Sidebar nav is built via `getNavigation(role)` from `src/lib/navigation.ts`; `navByRole` maps each role to its nav items.
   - Role badge colors via `roleAccentColours` in `src/components/ui/badge.tsx`:
     - super_admin = `#DC2626` (red), hospital_admin = `#6D28D9` (purple), doctor = `#1D6FA4` (blue)
     - nurse = `#059669` (green), lab_technician = `#D97706` (amber), receptionist = `#0B8A96` (teal)
     - pharmacy_technician = `#10B981` (emerald), radiology_technician = `#6366F1` (indigo)
     - billing_staff = `#0EAFBE` (cyan), ward_clerk = `#8B5CF6` (violet)

4. **Internationalization:** Client-side i18n via `src/lib/i18n/` (en, fr, ak, es); locale persisted in `localStorage` (`medsync_locale`).

5. **Tailwind CSS 4:** Uses PostCSS; fonts (DM Sans, DM Mono, Sora) loaded via `next/font`.

6. **Hooks pattern:** Each feature has a custom hook. All call `createApiClient()` internally for auth/token handling.

7. **TypeScript strict mode:** All files typed; `src/lib/types.ts` defines common types (User, Patient, Hospital, Encounter, etc.). `UserRole` union type covers all 10 roles.

### Data Models & Relationships

**Core (governance):**
- `Hospital` — Registration, facility type (Ghana referral hierarchy), region, NHIS code, `country` (data residency), `ip_subnets` (adaptive MFA), soft-delete fields
- `Ward` — Belongs to Hospital; `ward_type` (general/icu/maternity/paediatric/surgical/emergency)
- `Bed` — Belongs to Ward; status (available/occupied/reserved/maintenance)
- `Department` — OPD, Neuro, Radiology, etc.; per-hospital
- `LabUnit` — Hematology, Chemistry, Microbiology, etc.; routes lab orders
- `User` — Staff account; 10 roles (below); hospital, ward, department_link, lab_unit; adaptive MFA fields; 3-tier password recovery fields
- `TrustedDevice` — Device fingerprint for adaptive MFA; 30-day sliding expiry
- `AuditLog` — All actions logged; HMAC hash-chain for tamper-evidence

**User roles (10 total):**
`super_admin`, `hospital_admin`, `doctor`, `nurse`, `receptionist`, `lab_technician`, `pharmacy_technician`, `radiology_technician`, `billing_staff`, `ward_clerk`

**Facility-owned clinical data:**
- `Patient` — Demographics (Ghana Health ID, name, DOB, etc.); PHI fields encrypted at rest
- `PatientAdmission` — Admission to a ward; scoped to hospital + ward
- `Encounter` — Clinical visit; has `hospital`, `patient`, `provider`; clinical text fields encrypted
- `MedicalRecord` — Container for clinical records per encounter
- `Diagnosis`, `Prescription`, `Vital`, `LabOrder`, `LabResult`, `NursingNote` — Clinical records; PHI fields encrypted

**Pharmacy & CDS:**
- `ClinicalRule` — Drug-drug interaction, drug-allergy, renal dosing, duplicate therapy rules
- `CdsAlert` — Alert triggered when prescription/diagnosis matches a rule
- `DrugStock` — Drug inventory tracked by batch
- `Dispensation` — Record of medication dispensed
- `StockMovement` — Audit trail for all stock changes
- `StockAlert` — Low-stock or expiring medication alert

**Global/Interop (shared across hospitals):**
- `GlobalPatient` — Unique person identity (GPID); PHI encrypted; `data_residency_country` + `data_residency_locked` for NDPA enforcement
- `FacilityPatient` — Links a `GlobalPatient` to a specific hospital's `Patient`
- `Consent` — Hospital A grants access to Hospital B; scope (SUMMARY/FULL_RECORD), expiration
- `Referral` — Cross-hospital referral; status (pending/accepted/completed/rejected)
- `BreakGlassLog` — Emergency access record; last 15 minutes, fully audited

### Common Patterns

**Password validation (backend & frontend alignment):**
- Backend: `api.password_policy.validate_password()` enforces 5 rules.
- Frontend: `src/lib/password-policy.ts` mirrors same rules for UX validation.
- Backend is the authority; frontend validation is UX only.

**Hospital context in UI:**
- Sidebar and TopBar show: "Operating in: [Hospital Name]"
- Super Admin shows "All hospitals" if no view-as hospital is selected; can switch via `setViewAs()` (sends `X-View-As-Hospital` header to API for scoped auditing)
- Context is **not a dropdown** for regular users; it's read-only and determined by user profile

**Ward-scoped access (Nurse):**
- Nurse can see only patients admitted to their assigned ward.
- Query uses `PatientAdmission` with `nurse.ward_id` and `discharged_at IS NULL`.
- Nurse cannot create/edit records in other wards.

**Lab-unit-scoped access (Lab Technician):**
- Lab technician has an optional `lab_unit` FK; views/serializers restrict their queue to orders routed to their unit.

**Cross-facility view:**
- Doctor/Hospital Admin can search globally but can only **view** cross-facility records if consent/referral/break-glass condition is met.
- Backend response includes metadata: `cross_facility_scope` (SUMMARY/FULL_RECORD) in audit log.

---

## Quick Reference

| Task | Command |
|------|---------|
| Start backend | `cd medsync-backend && .venv\Scripts\activate && python manage.py runserver` |
| Start frontend | `cd medsync-frontend && npm run dev` |
| Run backend tests | `python -m pytest api/tests/ -v` |
| Run frontend unit tests | `npm run test` |
| Run Playwright e2e | `npx playwright test` |
| Lint frontend | `npm run lint` |
| Check backend health | `curl http://localhost:8000/api/v1/health` |
| Apply migrations | `python manage.py migrate` |
| View migrations | `python manage.py showmigrations` |
| Seed dev data | `python manage.py setup_dev` |
| Seed NHIS demo | `python manage.py seed_nhis_demo` |
| Check RBAC coverage | `python manage.py check_rbac_coverage` |
| Get dev TOTP code | `python manage.py dev_totp_code <email>` |
| Create superuser | `python manage.py createsuperuser` |

---

## Documentation References

All documentation lives in `docs/` as an eight-chapter student portfolio:

| Chapter | File | Contents |
|---------|------|----------|
| 0 | `docs/0_background_study.md` | Literature review, Ghana health system context, prior work |
| 1 | `docs/1_project_overview.md` | Project goals, functional requirements, NDPA/HIPAA constraints, role-dashboard matrix |
| 2 | `docs/2_system_architecture.md` | Three-tier architecture, multi-tenancy query isolation, TenantManager, Super Admin projection |
| 3 | `docs/3_database_design.md` | Relational schemas, field-level AES-256 encryption, legal retention calculator |
| 4 | `docs/4_security_and_compliance.md` | MFA pathways (TOTP/email OTP/passkey), adaptive MFA, account lockout, trusted devices, step-up OTP, tamper-evident audit log |
| 5 | `docs/5_interoperability_and_workflows.md` | GPID identity matching, consent scopes, referral state machine, Break-Glass, data residency |
| 6 | `docs/6_developer_manual.md` | Local setup, env config, migration/seed commands, Pytest/Vitest/Playwright test suites |
| 7 | `docs/7_evaluation_and_future_work.md` | Strengths, concurrency solutions, mock boundaries, future health-network integrations |

**For reviewers:** Start with chapters 1–2 for system context, chapter 4 for security, chapter 6 for setup/verify commands.

---

## Important Notes for Future Work

1. **Never commit `.env` files** — Database credentials and secrets are in environment variables, not git.
2. **Audit logging is mandatory** — Always log sensitive actions via `AuditLog.log_action()`. Sanitize `resource_id` to avoid logging PHI.
3. **Backend is the authority** — All access control is enforced server-side. The UI may hide or show controls, but the API decides what's allowed.
4. **PHI fields must be created encrypted** — When writing or squashing migrations, always define PHI fields with `django_cryptography.fields.encrypt()` in the `CreateModel` block. Never create plain then `AlterField` to encrypted in the same migration.
5. **Test in multi-hospital scenario** — When adding features, test with users from different hospitals to ensure scoping is correct.
6. **Token/session security is critical** — Refresh token rotation, blacklisting on logout, and MFA are core to healthcare security. Do not weaken these. Tokens live in sessionStorage only (no localStorage).
7. **Password policy is strict** — 12+ chars, uppercase, lowercase, digit, symbol, no reuse of last 5. Frontend validation mirrors backend; backend is the authority.
8. **All 10 roles must be covered** — When adding new views or permissions, run `python manage.py check_rbac_coverage` to verify RBAC coverage. The fail-closed mode (`PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=True`) blocks unknown endpoints by default.
9. **WSGI only** — The app runs under Gunicorn/WSGI. Channels and WebSocket are not installed; do not add async consumer code.
10. **Data residency** — When adding cross-facility access logic, always check `GlobalPatient.data_residency_locked` and compare `Hospital.country` against `GlobalPatient.data_residency_country` before granting access.
