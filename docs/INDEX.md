# MedSync EMR Documentation Index

**Last Updated:** June 2026
**Stack:** Django (gunicorn WSGI) + Next.js + Neon PostgreSQL — no Celery, Redis, or Daphne

---

## 🏗️ Architecture & Design

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Complete system design, multi-tenancy, authentication, interoperability (START HERE)

---

## 🚀 Deployment & Operations

- **[DEPLOY_RUNBOOK.md](DEPLOY_RUNBOOK.md)** — ⭐ Quick deployment reference (Docker, Railway, Nginx, cron)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Full deployment guide (Railway, Vercel, Neon setup)
- **[GO_NO_GO_CHECKLIST.md](GO_NO_GO_CHECKLIST.md)** — Production go/no-go checklist (complete Tier 1 before real PHI)
- **[Deployment/NEON_REGION_SELECTION_FIX.md](Deployment/NEON_REGION_SELECTION_FIX.md)** — Database region (`aws-af-south-1` / Africa/Cape Town)
- **[ADMIN_RUNBOOK.md](ADMIN_RUNBOOK.md)** — Hospital admin operational tasks
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Common issues and solutions
- **[BACKUP_STRATEGY.md](BACKUP_STRATEGY.md)** — Data protection and recovery procedures

---

## 🔐 Security & Compliance

- **[Security/SECURITY_AUDIT_SUMMARY.md](Security/SECURITY_AUDIT_SUMMARY.md)** — High-level security findings
- **[Security/SECURITY_AUDIT_INDEX.md](Security/SECURITY_AUDIT_INDEX.md)** — Audit documentation map
- **[Security/SECURITY_AUDIT_PASSWORD_SYSTEM.md](Security/SECURITY_AUDIT_PASSWORD_SYSTEM.md)** — Password policy implementation
- **[Security/SECURITY_AUDIT_ADDENDUM.md](Security/SECURITY_AUDIT_ADDENDUM.md)** — Follow-up security fixes
- **[Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md](Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md)** — MFA requirement (mandatory for all clinical roles)
- **[Security/JWT_ALGORITHM_SECURITY_FIX.md](Security/JWT_ALGORITHM_SECURITY_FIX.md)** — JWT security model
- **[Security/JWT_ALGORITHM_SECURITY_AUDIT.md](Security/JWT_ALGORITHM_SECURITY_AUDIT.md)** — Detailed JWT analysis

---

## 🤖 AI / Discharge Summary

The old `api/ai/` multi-agent module has been removed. The only active AI feature is the
**LLM-powered discharge summary** (`POST /api/v1/encounters/<id>/generate-discharge-summary`,
doctor-only), implemented in `api/services/discharge_service.py` and `api/services/llm_client.py`.

**Configuration:**
| Env var | Purpose |
|---|---|
| `LLM_MODE=bedrock` | Enable real AWS Bedrock inference (required in production) |
| `LLM_MODE=mock` | Free local-dev mode (blocked in production — set `DEBUG=True` to allow) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | Required when `LLM_MODE=bedrock` |
| `BEDROCK_MODEL_ID` | Default: `eu.anthropic.claude-sonnet-4-6` |

---

## 🩺 Mock / Stub Behavior

Systems that return fake data unless configured:

| System | Config to enable real mode | Fallback behavior |
|---|---|---|
| NHIS eligibility / claims | `NHIS_API_KEY` env var | Returns mock "approved" responses; logs a warning |
| LLM discharge summary | `LLM_MODE=bedrock` + AWS creds | In `DEBUG=True` dev: returns mock text. In production (`DEBUG=False`): returns HTTP 503 |
| Outbound email | `EMAIL_HOST` + SMTP vars | Prints to console (guarded against silent prod failures) |

---

## 🔌 Partially Wired Features (backend live, not yet in nav)

These features have fully routed backend endpoints but are not yet surfaced in the main
navigation. They are reachable by direct URL or API call. Decisions on wiring them into
the UI are tracked separately.

| Feature | Backend routes | Frontend component |
|---|---|---|
| Passkeys / WebAuthn | `auth/passkey/*` (10 routes) | `components/features/passkey/`, `settings/security/passkeys` |
| CDS Alerts | `cds-alerts/*` | `components/features/cds/CdsAlertsPanel.tsx`, `hooks/use-cds-alerts.ts` |
| NHIS Claims UI | `billing/nhis-claim`, `billing/invoices/.../submit-nhis` | `components/features/clinical/NhisClaimsDashboard.tsx` |
| FHIR / HL7 export | `fhir/*`, `hl7/*` (12 routes) | `hooks/use-fhir-export.ts` |
| Pharmacy Dashboard | `pharmacy-stock/*` | `components/features/pharmacy/PharmacyDashboard.tsx`, `PharmacyStockManager.tsx` |
| Batch operations admin | `batch-import/*`, `bulk-invitations/*` | `app/(dashboard)/admin/batch-operations/` |
| Shift management admin | `shifts/*` | `app/(dashboard)/admin/shift-management/` |
| Overtime reporting | `shifts/overtime-report` | `app/(dashboard)/admin/overtime-tracking/` |

---

## 📋 Features & Permissions

- **[Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md](Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md)** — Permissions matrix by module and role
- **[Features/ROLE_BASED_USERS_PERMISSIONS_UI.md](Features/ROLE_BASED_USERS_PERMISSIONS_UI.md)** — Frontend UI elements and access control
- **[Features/QUICK_REFERENCE_STATE_MACHINES.md](Features/QUICK_REFERENCE_STATE_MACHINES.md)** — State machines for referrals, lab orders, visits
- **[Features/SAFETY_IMPLEMENTATION_REFERENCE.md](Features/SAFETY_IMPLEMENTATION_REFERENCE.md)** — Clinical safety (allergies, alerts, MEWS)
- **[Features/RATE_LIMITING_FIXES_DETAILED.md](Features/RATE_LIMITING_FIXES_DETAILED.md)** — Rate limiting configuration
- **[Features/PERFORMANCE_FIXES.md](Features/PERFORMANCE_FIXES.md)** — Performance tuning

---

## 📖 API Reference

- **[medsync-backend/docs/API_REFERENCE.md](../medsync-backend/docs/API_REFERENCE.md)** — Complete API endpoint documentation (canonical)
- **[OPENAPI_SETUP.md](OPENAPI_SETUP.md)** — OpenAPI/Swagger configuration

---

## 🧭 How to Use This Documentation

### New Developers
1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design and multi-tenancy
2. **[DEPLOY_RUNBOOK.md](DEPLOY_RUNBOOK.md)** — Local development setup
3. **[medsync-backend/docs/API_REFERENCE.md](../medsync-backend/docs/API_REFERENCE.md)** — Available endpoints

### DevOps / Infrastructure
1. **[DEPLOY_RUNBOOK.md](DEPLOY_RUNBOOK.md)** — Quick deployment reference
2. **[DEPLOYMENT.md](DEPLOYMENT.md)** — Full deployment guide
3. **[GO_NO_GO_CHECKLIST.md](GO_NO_GO_CHECKLIST.md)** — Pre-live checklist
4. **[Deployment/NEON_REGION_SELECTION_FIX.md](Deployment/NEON_REGION_SELECTION_FIX.md)** — Database region

### Security / Compliance
1. **[Security/SECURITY_AUDIT_SUMMARY.md](Security/SECURITY_AUDIT_SUMMARY.md)** — Overview of findings
2. **[Security/JWT_ALGORITHM_SECURITY_FIX.md](Security/JWT_ALGORITHM_SECURITY_FIX.md)** — Auth security
3. **[Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md](Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md)** — MFA policy

### Clinical Leaders
1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — System capabilities overview
2. **[Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md](Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md)** — Access control by role
