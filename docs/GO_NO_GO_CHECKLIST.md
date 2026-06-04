# MedSync EMR — Production Go / No-Go Checklist

Work through tiers **in order**. Do not process real patient PHI until every **Blocking** item is checked.

**Honest readiness (~70%):** Clinical data integrity is strong. Deployability, security audit readiness, and full Ghana legal workflow still have fixable gaps below.

---

## Tier 1 — Blocking (before any real patient data)

| # | Item | Owner | Done |
|---|------|-------|------|
| 1 | Rotate any keys ever committed to git (`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`) | Security | ☐ |
| 2 | `DEBUG=False` in production; `ENV=production` | DevOps | ☐ |
| 3 | All required secrets set — placeholder `CHANGE_ME` values blocked at startup | DevOps | ☑ |
| 4 | Argon2 password hashing active (`PASSWORD_HASHERS`) | Backend | ☑ |
| 5 | JWT rotation + short access token lifetime enforced (15 min default, configurable) | Backend | ☑ |
| 6 | Anomaly detection: in-process only (no Redis/Celery — gunicorn single-process) | Backend | ☑ |
| 7 | `LLM_MODE=bedrock` in production (mock guard passes) | Backend | ☑ |
| 8 | Django admin on non-guessable `ADMIN_URL` — startup blocked if left as `admin/` | Security | ☑ |
| 9 | TLS termination (HTTPS only); HSTS enabled — Django enforces redirect; wire TLS at proxy | DevOps | ☐ |
| 10 | CORS locked to known frontend origins — startup blocked if wildcard or internal origin | Backend | ☑ |
| 11 | ~~Redis `requirepass` + TLS~~ — N/A: Redis removed; stack is gunicorn WSGI, no workers | DevOps | N/A |
| 12 | ~~Flower behind basic auth~~ — N/A: Celery/Flower removed from stack | DevOps | N/A |
| 13 | Database backups automated + restore tested quarterly | DevOps | ☐ |
| 14 | Health endpoint reports real backup status (not fake `ok`) | Backend | ☑ |
| 15 | Container runs as non-root (`USER medsync`) | DevOps | ☑ |
| 16 | gunicorn WSGI (not `runserver`) in production image | DevOps | ☑ |
| 17 | `python manage.py setup_production` succeeds on staging DB | DevOps | ☑ |
| 18 | Pre-deploy migrations run in CI/CD | DevOps | ☑ |
| 19 | Secrets scanner in CI + pre-commit hook (`block-insecure-secrets`) | Security | ☑ |
| 20 | Penetration test or formal security assessment scheduled | Security | ☐ |

---

## Tier 2 — High (before first hospital goes live)

| # | Item | Owner | Done |
|---|------|-------|------|
| 21 | `railway.toml` / deploy manifest reviewed for target environment | DevOps | ☑ |
| 22 | Nginx (or cloud LB) config deployed with rate limits | DevOps | ☑ |
| 23 | `collectstatic` in image; static served correctly | DevOps | ☑ |
| 24 | ~~Celery worker + beat~~ — N/A: removed; no-show cron runs as host cron (see `deploy/cron/`) | DevOps | N/A |
| 25 | Structured JSON logging shipped to aggregation | DevOps | ☑ |
| 26 | Sentry DSN configured for backend + frontend | DevOps | ☐ |
| 27 | FHIR `GET /fhir/metadata` CapabilityStatement live | Backend | ☐ |
| 28 | Consent withdrawal fields + audit on revoke | Backend | ☐ |
| 29 | NDPA DSAR + data deletion request workflows | Compliance | ☐ |
| 30 | Record retention guards on soft-delete | Backend | ☐ |
| 31 | Notifiable disease reporting pipeline | Clinical | ☐ |
| 32 | NHIS integration credentials (non-stub) | Integrations | ☐ |
| 33 | Patient portal minimum viable (view own results) | Product | ☐ |
| 34 | Session idle timeout wired (`InactivityModal`) | Frontend | ☐ |
| 35 | pip-audit + npm audit clean or accepted exceptions documented | Security | ☑ |
| 36 | Test coverage ≥70% enforced in CI | QA | ☐ |
| 37 | Operations runbook read by on-call (`docs/OPERATIONS_RUNBOOK.md`) | DevOps | ☐ |
| 38 | Incident response plan + contact tree | Security | ☐ |
| 39 | Staff security awareness training logged | Compliance | ☐ |
| 40 | Ghana Health ID verification on registration (when API available) | Integrations | ☐ |

---

## Tier 3 — Medium (within 30 days of operation)

| # | Item | Owner | Done |
|---|------|-------|------|
| 41 | DHIMS-2 monthly export module | Clinical | ☐ |
| 42 | FHIR write endpoints (Observation, Patient update) | Backend | ☐ |
| 43 | SMART on FHIR `/.well-known/smart-configuration` | Backend | ☐ |
| 44 | Object-level permissions (`django-guardian`) | Backend | ☐ |
| 45 | Barcode wristband scan on mobile PWA | Frontend | ☐ |
| 46 | Push notifications for critical results | Frontend | ☐ |
| 47 | Offline conflict resolution UI | Frontend | ☐ |
| 48 | Hospital operations analytics dashboard | Product | ☐ |
| 49 | Telemedicine on referral detail | Product | ☐ |
| 50 | Twi locale on patient-facing screens | Product | ☐ |
| 51 | WCAG 2.1 AA axe audit remediation | UX | ☐ |
| 52 | ML retraining plan on Ghana real-world data | ML | ☐ |
| 53 | Disaster recovery RTO/RPO documented | DevOps | ☐ |
| 54 | Quarterly backup restore drill | DevOps | ☐ |

---

## Four production tests (summary)

| Test | Pass today? | Notes |
|------|-------------|-------|
| Deployable by hospital IT | Partial | Docker + Railway manifest + nginx samples added; IT still must configure secrets, TLS, DB |
| Passes security audit | Partial | Strong baseline; admin URL, object-level perms, pen test still open |
| Clinical data trustworthy | **Yes** | Encryption, audit chain, CDS, optimistic locking |
| Ghana legal requirements | Partial | NDPA/FHIR gaps; consent withdrawal in progress |

---

*Last updated: June 2026 — scope-tighten branch. Open Tier 1 blockers: #1 (key rotation), #2 (DEBUG=False), #9 (TLS at proxy), #13 (DB backup), #20 (pen test). Reconcile ☑ items after each release.*
