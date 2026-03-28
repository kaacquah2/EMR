# GitHub Copilot Instructions for MedSync EMR

MedSync is a **centralized, multi-hospital Electronic Medical Records (EMR) system** built for Ghana's inter-hospital network. It provides role-based access, clinical records management, patient admissions, lab orders, referrals, and cross-facility record sharing with consent/break-glass emergency access.

## Repository Structure

- **`medsync-backend/`** — Django 4.2+ REST API with JWT+TOTP MFA, multi-tenancy, audit logging, FHIR/HL7 interop
- **`medsync-frontend/`** — Next.js 16 (App Router) + React 19 + TypeScript frontend with role-based dashboard
- **`docs/`** — Detailed architecture and governance documentation (Multi_Tenancy_Architecture.md, Governance_Model.md, etc.)

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
python manage.py setup_dev  # Load seed data
python manage.py runserver

Created super admin: admin@medsync.gh / Admin123!@#
Created doctor: doctor@medsync.gh / Doctor123!
Created doctor2: doctor2@medsync.gh / Doctor234!
Created hospital admin: hospital_admin@medsync.gh / HospitalAdmin123!
Created nurse: nurse@medsync.gh / Nurse123!@#
Created receptionist: receptionist@medsync.gh / Receptionist123!@#
Created lab tech: lab_technician@medsync.gh / LabTech123!@#
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

**Health check (when running):**
```bash
# GET http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health
```

**Config:** Uses `python-decouple` for environment variables (`.env` file). Key vars: `DEBUG`, `DATABASE_URL`, `SECRET_KEY`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `CORS_ALLOWED_ORIGINS`.

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
npm run test        # Run all tests once
npm run test:watch  # Watch mode
```

**Building & running:**
```bash
npm run build  # Production build
npm run start  # Start production server
npm run lint   # ESLint check
```

**Config:** Environment file sets `NEXT_PUBLIC_API_URL` (public API endpoint). Frontend expects backend at `http://localhost:8000/api/v1` by default.

---

## High-Level Architecture

### Multi-Tenancy: Hospital-Scoped Access

**Core principle:** "Every user belongs to a hospital; data is scoped by hospital."

- **User model:** Each user has `role`, `hospital_id`, and optional `ward_id`. Hospital assignment is **not chosen by the user** at login—it's fixed on the account.
- **Data ownership:** All clinical data (encounters, admissions, appointments, lab orders) stores `hospital_id`. Non-super_admin users see only their hospital's data.
- **Super Admin:** No hospital assigned; can see all data (with optional `X-View-As-Hospital` header for auditing).
- **Hospital Admin:** Assigned to one hospital; manages that hospital's staff and audit logs.

**Key enforcement:** `api.utils.get_patient_queryset()` and `can_access_cross_facility()` filter all queries based on user's hospital and role.

### Cross-Facility Interoperability (HIE Layer)

The system supports shared medical records across hospitals via:

1. **Global Patient Registry** — Unique identifier (GPID) for a patient across all hospitals.
2. **Consent** — Hospital A can consent to Hospital B accessing their records; scope is `SUMMARY` (demographics only) or `FULL_RECORD` (includes clinical data).
3. **Referrals** — Doctor at Hospital A can refer a patient to Hospital B; referral status is tracked and accepted.
4. **Break-Glass Emergency Access** — Any authorized user can access records in an emergency (last 15 minutes, fully logged/audited).

**Access control:** All enforced server-side in backend; API is the authority. Logged in `AuditLog` with action `VIEW`, `CREATE_REFERRAL`, `EMERGENCY_ACCESS`, etc.

### Authentication & Security

- **JWT + TOTP MFA:** Simple JWT for access/refresh tokens; TOTP (Time-based OTP) for MFA via django-otp + pyotp.
- **Access token TTL:** 15 minutes (configurable via `JWT_ACCESS_MINUTES`); refresh token 7 days.
- **Token blacklist:** On logout or refresh rotation, tokens are blacklisted server-side (Simple JWT blacklist).
- **Password policy:** 12+ chars, uppercase, lowercase, digit, symbol; no reuse of last 5 passwords (enforced via `api.password_policy.validate_password()` and `UserPasswordHistory` model).

**Frontend behavior:** Keeps tokens in memory/sessionStorage, retries once on 401 by refreshing access token, sends refresh token to `POST /auth/logout` for revocation.

### Database

- **Development:** SQLite (auto-used when `DEBUG=True` and `DATABASE_URL` unset).
- **Production:** PostgreSQL via Neon (connection string set in `DATABASE_URL` env var; backend uses `dj-database-url` and forces `sslmode=require`).

**Migrations:** Two apps (`patients`, `records`) have two-phase migrations: `_0001_blueprint_*` (legacy tables) + `_0002_*` (new tables like ClinicalAlert, Encounter).

---

## Key Conventions

### Backend (Django/DRF)

1. **Facility scoping:** Use `get_effective_hospital(request)` to get the hospital context; return `user.hospital` for non-super_admin, None for super_admin with no hospital.

2. **View structure:** Views in `api/views/` are organized by feature (e.g. `patient_views.py`, `record_views.py`, `admin_views.py`). Most return 403 if user role is not authorized (see `_block_non_clinical_roles()` for examples).

3. **Audit logging:** Call `AuditLog.log_action()` after create/update/delete operations. Always sanitize `resource_id` via `sanitize_audit_resource_id()` to avoid logging PHI or tokens.

4. **Serializers:** In `api/serializers.py`, all use DRF's standard patterns. Clinical record create endpoints enforce `patient.registered_at.id == user.hospital.id`.

5. **Password policy:** Import `api.password_policy.validate_password()` and `check_password_reuse()` for account activation and password reset. Use `UserPasswordHistory` to track last 5 hashes.

6. **FHIR/HL7:** Read-only endpoints in `api/views/fhir_views.py` and `api/views/hl7_views.py`. Map internal models (Patient, Encounter, Diagnosis, Prescription, Vital) to FHIR resources.

7. **Error codes:** Return 400 for validation, 403 for permission, 404 for not found, 503 for DB down (health endpoint).

### Frontend (Next.js/React)

1. **File structure:** 
   - `app/` — Pages (auth routes in `(auth)/`, authenticated app in `(dashboard)/`)
   - `components/` — Organized by `layout/` (Sidebar, TopBar), `features/` (domain-specific), `ui/` (reusable)
   - `hooks/` — API integration (one per feature: `use-patients.ts`, `use-admin.ts`, etc.)
   - `lib/` — Utilities (`api-client.ts`, `auth-context.tsx`, `types.ts`, `i18n/`, password validation)

2. **API client:** `lib/api-client.ts` provides `createApiClient()` with `getToken()`, `setToken()`, `onRefresh()` for token management. Uses `fetch` with headers, retries on 401 with refresh.

3. **Role-based UI:** 
   - Import `useAuth()` (from `lib/auth-context.tsx`) to get `user.role` and `user.hospital`.
   - Sidebar nav is built from `navByRole[user.role]` (sidebar logic for each role).
   - Role badge colors via `roleAccentColours` object (super_admin = red, hospital_admin = purple, doctor = blue, nurse = green, lab_technician = amber).

4. **Internationalization:** Client-side i18n via `lib/i18n/` (en, fr, ak, es); locale persisted in `localStorage` (`medsync_locale`).

5. **Tailwind CSS 4:** Uses PostCSS; fonts (DM Sans, DM Mono, Sora) loaded via `next/font`.

6. **Hooks pattern:** Each feature has a custom hook (e.g. `use-patients.ts` with `getPatients()`, `registerPatient()`, etc.). All call `createApiClient()` internally for auth/token handling.

7. **TypeScript strict mode:** All files typed; `lib/types.ts` defines common types (User, Patient, Hospital, Encounter, etc.).

### Data Models & Relationships

**Core EMR (facility-owned):**
- `Patient` — Demographics (Ghana Health ID, name, DOB, etc.)
- `PatientAdmission` — Admission to a ward; scoped to hospital + ward
- `Encounter` — Clinical visit; has `hospital`, `patient`, `provider` (doctor/nurse)
- `MedicalRecord` — Diagnosis, prescription, vital sign, lab order, nursing note
- `Diagnosis`, `Prescription`, `Vital`, `LabOrder`, `LabResult`, `NursingNote` — Clinical records

**Global/Interop (shared):**
- `GlobalPatient` — Unique person ID; links to multiple `FacilityPatient` (one per hospital)
- `Consent` — Hospital A grants access to Hospital B for a patient; scope (SUMMARY/FULL_RECORD), expiration
- `Referral` — Hospital A refers patient to Hospital B; tracks status (pending/accepted/completed/rejected)
- `BreakGlassLog` — Emergency access use; last 15 minutes, fully audited

**Governance:**
- `Hospital` (aka Facility) — Hospital registration (name, code, location, active status)
- `User` — Staff account; role (super_admin, hospital_admin, doctor, nurse, lab_technician, receptionist), hospital, ward
- `AuditLog` — All actions logged: VIEW, CREATE, UPDATE, DELETE, EMERGENCY_ACCESS, etc.; sanitized `resource_id`

### Common Patterns

**Password validation (backend & frontend alignment):**
- Backend: `api.password_policy.validate_password()` enforces 5 rules.
- Frontend: `lib/password-policy.ts` mirrors same rules for UX validation.
- Backend is the authority; frontend validation is UX only.

**Hospital context in UI:**
- Sidebar and TopBar show: "Operating in: [Hospital Name]"
- Super Admin shows "All hospitals" if no hospital assigned
- Context is **not a dropdown**; it's read-only and determined by user profile

**Ward-scoped access (Nurse):**
- Nurse can see only patients admitted to their assigned ward.
- Query uses `PatientAdmission` with `nurse.ward_id` and `discharged_at IS NULL`.
- Nurse cannot create/edit records in other wards.

**Cross-facility view:**
- Doctor/Hospital Admin can search globally but can only **view** cross-facility records if consent/referral/break-glass condition is met.
- Backend response includes metadata: `cross_facility_scope` (SUMMARY/FULL_RECORD) in audit log.

---

## Quick Reference

| Task | Command |
|------|---------|
| Start backend | `cd medsync-backend && source .venv/bin/activate && python manage.py runserver` |
| Start frontend | `cd medsync-frontend && npm run dev` |
| Run backend tests | `python -m pytest api/tests/ -v` |
| Run frontend tests | `npm run test` |
| Check backend health | `curl http://localhost:8000/api/v1/health` |
| Login (dev) | Use any dev user from `setup_dev` (e.g. doctor@medsync.gh / Doctor123!@#); TOTP secret in backend README |
| View migrations | `python manage.py showmigrations` |
| Create superuser | `python manage.py createsuperuser` |

---

## Documentation References

For deeper understanding, see `docs/`:

- **Multi_Tenancy_Architecture.md** — How hospital scoping works; user/data model
- **Governance_Model.md** — Super Admin vs Hospital Admin responsibilities and workflows
- **Codebase_Audit_Report.md** — Security review, code structure, and post-audit doc updates (README reviewer sections, tests, receptionist/register)
- **Access_Governance.md** — Cross-facility access rules in detail
- **Operational_Model_Integration.md** — Workflow routing and role responsibilities
- **Backup_And_Disaster_Recovery.md** — Data protection strategy
- **Monitoring_And_Alerting.md** — Observability and health checks

**For reviewers:** Backend and frontend READMEs include a **For reviewers** section (what the system is, quick verify commands, key docs, dev credentials). Use those sections plus `docs/Codebase_Audit_Report.md` for a structured review.

---

## Important Notes for Future Work

1. **Never commit `.env` files** — Database credentials and secrets are in environment variables, not git.
2. **Audit logging is mandatory** — Always log sensitive actions via `AuditLog.log_action()`. Sanitize `resource_id` to avoid logging PHI.
3. **Backend is the authority** — All access control is enforced server-side. The UI may hide or show controls, but the API decides what's allowed.
4. **Test in multi-hospital scenario** — When adding features, test with users from different hospitals to ensure scoping is correct.
5. **Token/session security is critical** — Refresh token rotation, blacklisting on logout, and MFA are core to healthcare security. Do not weaken these.
6. **Password policy is strict** — 12+ chars, uppercase, lowercase, digit, symbol, no reuse of last 5. Frontend validation mirrors backend; backend is the authority.
