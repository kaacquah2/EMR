# MedSync EMR - Comprehensive Project Documentation

**Status:** ~70% production-ready — clinical data integrity is strong; deployability, security hardening, and full Ghana regulatory workflows have documented gaps. See the [Evaluation & Future Work](docs/7_evaluation_and_future_work.md) chapter for the current production gap list.

MedSync is a centralized, multi-hospital Electronic Medical Records (EMR) system for Ghana's inter-hospital network. It provides comprehensive patient and clinical records management, role-based access, inter-hospital interoperability (consent, referrals, break-glass), and HIPAA-compliant audit logging.

---

## Quick Links

- **Backend:** `medsync-backend/README.md` — Django REST API setup, API reference, security details
- **Frontend:** `medsync-frontend/README.md` — Next.js frontend setup, role-based dashboards
- **Documentation index:** [docs/README.md](docs/README.md) — full chapter index (architecture, security, developer guide, evaluation)

---

## Project Structure

```
EMR/
├── medsync-backend/               # Django REST API
│   ├── README.md                  # Backend setup, API docs, security details
│   ├── api/                       # REST endpoints (33 view modules)
│   ├── core/                      # User, auth, audit models
│   ├── patients/                  # Patient & admission models
│   ├── records/                   # Clinical records (encounters, diagnoses, etc.)
│   ├── interop/                   # Cross-facility interop (referrals, consent, break-glass)
│   ├── requirements-local.txt     # Python deps (local/CI)
│   └── manage.py                  # Django CLI
│
├── medsync-frontend/              # Next.js 16 + React 19 frontend
│   ├── README.md                  # Frontend setup, routes, role matrix
│   └── src/
│       ├── app/                   # Pages (auth, dashboard, etc.)
│       ├── components/            # React components
│       ├── hooks/                 # Custom hooks (API integration)
│       └── lib/                   # Utilities, auth context, types
│
├── docs/                          # Portfolio documentation (see docs/README.md)
│   ├── 1_project_overview.md
│   ├── 2_system_architecture.md
│   ├── 3_database_design.md
│   ├── 4_security_and_compliance.md
│   ├── 5_interoperability_and_workflows.md
│   ├── 6_developer_manual.md
│   └── 7_evaluation_and_future_work.md
│
└── README.md                      # This file
```

---

## Technology Stack

| Component | Tech | Version |
|-----------|------|---------|
| **Backend Framework** | Django | 4.2+ |
| **Backend API** | Django REST Framework | 3.14+ |
| **Authentication** | JWT + TOTP MFA | Simple JWT + django-otp |
| **Database (Prod)** | PostgreSQL (Neon) | Latest |
| **Database (Dev)** | SQLite | - |
| **Frontend Framework** | Next.js | 16 (App Router) |
| **Frontend Library** | React | 19 |
| **Frontend Language** | TypeScript | 5 |
| **Styling** | Tailwind CSS | 4 |
| **E2E Testing** | Playwright | Latest |
| **Unit Testing** | Vitest / pytest | Latest |
| **FHIR/HL7** | Read-only REST endpoints | - |

---

## System Architecture

### Three-Tier Architecture

1. **Global Platform (Central)** �?? Global Patient Registry, Consent Records, Referral Requests, Break-Glass Logs
2. **Hospital Layer (Facility)** �?? Encounters, Clinical Records, Admissions, Lab Orders (owned by each hospital)
3. **Cross-Facility Layer (HIE)** �?? Consent-gated, Referral-based, and Emergency access audit trails

### Multi-Tenancy Model

- Every user belongs to exactly one hospital (assigned by system, not chosen)
- All queries scoped by `hospital_id`
- Super Admin has no hospital assignment (sees all data)
- Cross-facility access only via consent, referral, or break-glass (time-limited emergency access)
- Full audit trail on all cross-facility access

### Key Features

**Clinical:**
- �?? Patient registration and demographics
- �?? Clinical encounters and diagnoses
- �?? Prescriptions and medication management
- �?? Lab orders and results
- �?? Vital signs and nursing notes
- �?? Clinical alerts and warnings

**Administrative:**
- �?? Hospital onboarding and management
- �?? User management (staff, doctors, nurses, lab technicians)
- �?? Ward and bed management
- �?? Staff onboarding and bulk import
- �?? Role-based access control (10 roles)
- �?? Audit logging (17 action types, full context)

**Interoperability:**
- �?? Global Patient Registry (GPID - unique ID across hospitals)
- �?? Referral workflows (requests, acceptance, completion)
- �?? Consent management (SUMMARY or FULL_RECORD scope, with expiration)
- �?? Break-glass emergency access (time-limited, fully audited, last 15 minutes)
- �?? FHIR REST endpoints (read for Patient/Encounter/Condition/DiagnosticReport; write for MedicationRequest/Observation)
- �?? HL7 export capabilities

**Security:**
- �?? JWT + TOTP MFA authentication
- �?? Password policy (12+ chars, complexity, 5-password history)
- �?? Account lockout (5 attempts �?? 15 min lock)
- �?? Token rotation and blacklisting
- �?? HTTPS/HSTS, CSP headers, CSRF protection
- �?? Comprehensive audit logging with PHI sanitization
- �?�️ **Tier 1 hardening items remain** (see [Chapter 7](docs/7_evaluation_and_future_work.md))

---

## Current Status

### Production Readiness: ~70%

Clinical data integrity and core security are strong. Infrastructure hardening and Ghana regulatory workflows have remaining gaps. See [Chapter 7: Evaluation & Future Work](docs/7_evaluation_and_future_work.md) for the current gap list.

| Component | Status | Readiness |
|-----------|--------|-----------|
| **Core Features** | Complete | 100% |
| **Multi-Tenancy** | Complete | 100% |
| **Role-Based Access** | Complete | 100% |
| **Audit Logging** | Complete | 100% |
| **Security Fundamentals** | Complete | 100% |
| **Testing** | Complete | 100% |
| **Infrastructure/Monitoring** | Partial | 70% |
| **Deployment Hardening** | Partial | 60% |

### Completed Hardening (resolved during audit phases)
- Critical timing attacks on temp passwords fixed; rate limiting added
- Backup code constant-time comparison fixed; account lockout race fixed
- Database-backed rate limiting; CSP middleware; RBAC fail-closed mode
- PHI field-level encryption; audit chain with HMAC signatures
- WebAuthn/Passkeys; JWT rotation; Argon2 password hashing

### Remaining Tier 1 Blockers (before real patient data)
- Rotate any secrets that were ever committed to git
- Set `ADMIN_URL` to a non-guessable path in production
- TLS termination + HSTS at the host/proxy layer
- Automated database backups + quarterly restore test
- Formal penetration test scheduled

---

## Getting Started

### Backend Setup

```bash
cd medsync-backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-local.txt

# Setup database
python manage.py migrate
python manage.py setup_dev  # Load seed data

# Run dev server
python manage.py runserver
```

Backend runs on `http://localhost:8000/api/v1`

### Frontend Setup

```bash
cd medsync-frontend

# Install dependencies
npm install

# Setup environment
cp .env.example .env
# (NEXT_PUBLIC_API_URL defaults to http://localhost:8000/api/v1)

# Run dev server
npm run dev
```

Frontend runs on `http://localhost:3000`

### Running Tests

```bash
# Backend tests
cd medsync-backend
python -m pytest api/tests/ -v

# Frontend tests
cd medsync-frontend
npm run test
npm run test:e2e  # E2E tests (requires both servers running)
```

---

## Production Deployment History

### Phase 1: Critical Security Fixes
- [x] Fix timing attack on temp password
- [x] Add rate limiting to temp password endpoint
- [x] Implement server-side password change enforcement
- [x] Fix backup code constant-time comparison
- [x] Fix account lockout race condition
- [x] Implement database-backed rate limiting
- [x] Security test suite (100+ tests)

### Phase 2: High-Priority Fixes
- [x] Session cookie security flags (frontend + backend)
- [x] Test/fix MFA user throttle
- [x] E2E test coverage expansion
- [x] Load testing

### Phase 3: Compliance & Hardening
- [ ] Formal HIPAA compliance audit (planned — requires third-party auditor)
- [ ] Formal penetration test (planned — listed in Tier 1 blockers; see docs/7)
- [x] Final security review (self-review completed; formal pen test pending)
- [x] Monitoring & alerting setup
- [x] Field-level PHI encryption + HMAC audit chain hardening

### Phase 4: Pre-Production
- [x] Production deployment runbook
- [x] Team training
- [x] Incident response plan
- [x] Dry-run deployment
- [x] Render backend deployment and GitHub synchronization

---

## Documentation

- **Backend README:** `medsync-backend/README.md` — Setup, API routes, security, password policy, FHIR/HL7
- **Frontend README:** `medsync-frontend/README.md` — Setup, role-based dashboards, component structure
- **Portfolio docs:** [docs/README.md](docs/README.md) — 7-chapter documentation index covering architecture, security, interoperability, developer guide, and evaluation
## Key Roles & Access Levels

| Role | Hospital Scope | Main Responsibilities | Pages Access |
|------|-----------------|----------------------|--------------|
| **super_admin** | All hospitals | Onboard hospitals, manage admins, global audit | Superadmin dashboard, audit logs, hospital management |
| **hospital_admin** | Single hospital | Manage staff, approve requests, facility audit | Admin dashboard, staff management, audit logs |
| **doctor** | Single hospital | Patient management, records, referrals | Patients, encounters, orders, cross-facility access |
| **nurse** | Assigned ward | Patient care, admissions, vitals | Ward patients, admissions, clinical records |
| **lab_technician** | Single hospital | Lab orders, results | Lab orders, results management, analytics |
| **receptionist** | Single hospital | Appointments, check-in, demographic updates | Appointments, patient search |
| **pharmacy_technician** | Single hospital | Dispense medications, MAR | Pharmacy queue, dispensation, MAR |
| **radiology_technician** | Single hospital | Radiology orders, imaging | Radiology orders, results |
| **billing_staff** | Single hospital | Invoicing, payments, NHIS claims | Billing, invoices, reports |
| **ward_clerk** | Single hospital | Ward admin, bed management | Ward dashboard, bed assignments |

---

## Security Posture

### Strengths �??

- Multi-tenancy properly enforced (hospital_id scoping on all queries)
- Role-based access control working correctly
- JWT + TOTP MFA authentication
- Password policy (12+ chars, complexity, 5-password history)
- Account lockout protection
- Comprehensive audit logging with PHI sanitization
- Cross-facility access gated by consent/referral/break-glass
- HTTPS/HSTS, CSP headers, CSRF protection
- Break-glass access time-limited (15 min) and fully audited

### Open Gaps

Remaining Tier 1 blockers (see [Chapter 7](docs/7_evaluation_and_future_work.md) for full list):
- Key rotation if any secrets were committed to git
- Non-guessable Django admin URL in production (`ADMIN_URL` env var)
- TLS/HTTPS at host/proxy layer + HSTS
- Automated DB backup + quarterly restore drill
- Formal penetration test

### Next Steps

Work through the Tier 1 items in [Chapter 7: Evaluation & Future Work](docs/7_evaluation_and_future_work.md) before processing any real patient data.

---

## Support & Contact

**Questions about:**
- **Setup:** See README.md in `medsync-backend/` or `medsync-frontend/`
- **Architecture:** See `docs/` directory
- **Security:** See [docs/4_security_and_compliance.md](docs/4_security_and_compliance.md)
- **Current Status & Gaps:** See [docs/7_evaluation_and_future_work.md](docs/7_evaluation_and_future_work.md)
- **Developer Guide:** See [docs/6_developer_manual.md](docs/6_developer_manual.md)

---

## License & Compliance

This system is designed for Ghana's healthcare sector and must comply with:
- HIPAA (if used in US)
- Local Ghana healthcare regulations
- GDPR (if EU users access system)
- Data protection and privacy laws

All audit logging, consent management, and access control are designed to support compliance requirements.

---

**Last Updated:** June 2026  
**Production Readiness:** ~70% — clinical data integrity and security fundamentals are strong; infrastructure hardening and regulatory workflows have remaining gaps.  
**Next:** Work through Tier 1 items in [Chapter 7: Evaluation & Future Work](docs/7_evaluation_and_future_work.md) before processing real patient data.
