# MedSync EMR — Complete Master Prompt
## Full System Review: Architecture · Security · Clinical · Compliance · UX · AI/ML · Features

**Project:** Design and Implementation of a Secure Centralized Electronic Medical Records System for Inter-Hospital Access
**Stack:** Django REST Framework (Python 3.12) · Next.js 16 / React 19 · PostgreSQL · Redis · Celery · Docker
**Context:** Multi-hospital EMR for Ghana. Aligned against Ghana Digital Health Strategy 2023–2027, NDPA 2012, NHIA/NHIS requirements, FHIR R4, and HIPAA-equivalent standards.
**Codebase size:** ~73,777 lines Python · ~45,499 lines TypeScript/TSX · 340 Python files · 257 frontend files · 411 backend tests · 38 API view files

---

## PART 1 — INITIAL REVIEW SCORES

| Dimension | Score |
|---|---|
| Architecture | 90/100 |
| Security | 85/100 |
| Testing | 75/100 |
| Code quality | 82/100 |
| Observability | 78/100 |
| **Overall** | **83/100** |

---

## PART 2 — CONFIRMED STRENGTHS (do not break these)

- Clean 3-tier separation: Django REST API, Next.js frontend, Celery async workers
- FHIR-compliant read endpoints and HL7 interop layer in `interop/`
- Single-source-of-truth RBAC with `PERMISSION_MATRIX` in `shared/permissions.py` covering 10+ roles (super_admin, hospital_admin, doctor, nurse, receptionist, lab_technician, pharmacy_technician, radiology_technician, billing_staff, ward_clerk)
- JWT + TOTP MFA + WebAuthn/passkeys authentication stack
- `MustChangePasswordPermission`, break-glass emergency access with full audit trail
- Anomaly detection middleware (200 unique patients/hr threshold) — concept correct, implementation needs Redis
- Field-level PHI encryption via `django-cryptography` on all sensitive fields
- Comprehensive audit logging with 40+ action types: auth events, break-glass, role changes, cross-facility access, PHI views, anomalies
- HMAC-chained audit log signatures (tamper-evident chain)
- Clinical Decision Support (CDS) engine with Redis-cached rules, drug-drug interaction checking, allergy contraindications, renal dose adjustment, duplicate therapy detection
- 411 backend test cases across 50 test files: RBAC, PHI encryption, FHIR compliance, break-glass, MFA, rate limiting
- Full Docker Compose stack: postgres, redis, backend, celery, flower, frontend
- Sentry error tracking, Celery Beat scheduled tasks, health check endpoints
- React 19 + Next.js 16 App Router with SWR data fetching
- Playwright E2E tests, Vitest unit tests
- PWA support with service worker, IndexedDB offline store, sync engine
- GlobalPatient / FacilityPatient model for cross-hospital identity (GPID)
- Ghana-specific fields: `ghana_health_id`, `nhis_number`, `data_residency_country`, NDPA 2012 data residency controls
- `NHISClient` with circuit breaker for Ghana NHIA API integration (well-designed, needs real credentials)
- Optimistic locking (`record_version`) on `MedicalRecord` and `Prescription`
- Soft-delete + archival pattern on Hospital and Patient models
- Duplicate patient detection with `PotentialDuplicate` merge workflow
- Pharmacy stock management with reorder levels, expiry tracking
- `CircuitBreaker` pattern for external service calls
- `CommandPalette` with keyboard shortcuts
- Role-specific mobile bottom navigation
- Dark mode CSS variable system in `globals.css`
- Shift tracking (`ShiftBreakTracker`), bed grid with drag-and-drop
- `VitalsTrendChart` with normal range reference lines

---

## PART 3 — CRITICAL SECURITY ISSUES (fix before any real data)

### P0 — Fix immediately

**1. Anomaly detection uses in-process Python dict, not Redis**
- File: `api/middleware/anomaly_detection.py`
- Problem: `_access_tracker` is a module-level dict. In a multi-worker ASGI/Gunicorn deployment each worker has its own counter. A user can access 199 patients on each of 4 workers = 796 undetected PHI accesses.
- Fix: Migrate to Redis using `INCR`/`EXPIRE` pattern, same as the CDS rules cache. The code itself has a comment "in production, use Redis" — implement it.

**2. No Argon2 password hashing configured**
- Problem: No `PASSWORD_HASHERS` setting anywhere in `settings.py`. Django defaults to PBKDF2-SHA256. OWASP 2025 and the proposed new HIPAA Security Rule both mandate Argon2id.
- Fix: Add `PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher']` and `pip install argon2-cffi`. The second entry handles existing passwords during migration.

**3. No session idle timeout enforced**
- Problem: No `SESSION_COOKIE_AGE` and no JWT inactivity timeout. HIPAA requires automatic session termination after a period of inactivity. A clinician leaving a workstation logged in exposes all patient data.
- Fix: Reduce `ACCESS_TOKEN_LIFETIME` to 15 minutes with silent refresh on user activity. Add idle-detection middleware or frontend inactivity timer that calls `/auth/logout` after configurable inactivity period. The `InactivityModal.tsx` component exists in the frontend — wire it.

**4. LLM mock mode has no production guard**
- Problem: `LLM_MODE=mock` is the default in `llm_client.py`. If a production deployment omits `LLM_MODE=bedrock`, AI differential diagnosis and risk predictions silently return mock/fake clinical data — including the same fake "Community-acquired pneumonia" for every query. A clinician will act on it.
- Fix: Add a Django system check in `AppConfig.ready()`:
  ```python
  if os.environ.get('ENV') == 'production' and settings.LLM_MODE == 'mock':
      raise ImproperlyConfigured("LLM_MODE=mock is not permitted in production. Set LLM_MODE=bedrock.")
  ```

**5. Hardcoded secrets committed to public GitHub repo**
- Problem: `docker-compose.yml` contains `SECRET_KEY=django-insecure-dev-key` and `FIELD_ENCRYPTION_KEY=ci-test-encryption-key-32-chars-long-at-least` in plaintext. This is a public repository. These keys are compromised.
- Fix: Rotate both keys immediately. Reference `.env` file only: `SECRET_KEY=${SECRET_KEY}`. Add a pre-commit hook that rejects commits containing known insecure key strings.

### P1 — High priority

**6. No OpenAPI / Swagger documentation**
- No `drf-spectacular` or `drf-yasg`. The FHIR `CapabilityStatement` (`GET /fhir/metadata`) is completely missing — it's a mandatory FHIR R4 requirement. Without it no hospital or partner system can discover your API capabilities.
- Fix: Add `drf-spectacular`, wire `GET /fhir/metadata` returning a valid R4 CapabilityStatement listing all supported resources, search parameters, and operations.

**7. Consent model missing patient-initiated withdrawal**
- The `Consent` model has no `withdrawn_at`, `withdrawn_by`, or `withdrawal_reason` fields. Under NDPA 2012 §26 and HIPAA, a patient must be able to revoke consent at any time with an audited record.
- Fix: Add `withdrawn_at = models.DateTimeField(null=True, blank=True)`, `withdrawn_by = models.ForeignKey(User, ...)`, `withdrawal_reason = models.TextField(blank=True)`. Add a `withdraw()` method that sets these and flips `is_active=False`. Add audit log entry on withdrawal.

**8. FHIR layer is read-only — no write endpoints**
- All 7 FHIR views are GET only. No `POST /fhir/Observation`, `PUT /fhir/Patient`, or FHIR Batch/Transaction bundle support. This blocks real inter-hospital workflows where partner systems push results (lab systems, imaging systems, referral hubs).
- Fix: Implement FHIR write endpoints for at minimum: Patient (update demographics), Observation (lab result push), DiagnosticReport (imaging result push), Condition (diagnosis from external system).

**9. No SMART on FHIR / OAuth2 for third-party app authorization**
- No `/.well-known/smart-configuration` endpoint. Blocks any partner application from authenticating to your FHIR layer using the standard authorization flow.
- Fix: Implement SMART on FHIR launch protocol. Minimum: add the well-known configuration endpoint advertising your OAuth2 endpoints, supported scopes, and capabilities.

**10. Django admin has no IP restriction or custom URL**
- `/admin/` is accessible publicly in production. In an EMR this is a full-PHI exposure surface.
- Fix: Change the admin URL to a non-guessable path: `path(env('ADMIN_URL', default='admin/'), admin.site.urls)`. Add IP allowlist middleware or put behind VPN. Consider disabling Django admin entirely in production and using the super_admin role in your own UI.

**11. No object-level / row-level permissions**
- RBAC is enforced at the endpoint level but not at the row level. A doctor with `GET /patients/<pk>` access can technically query any patient UUID in their hospital even if not their treating physician.
- Fix: Add `django-guardian` for object-level permissions. Apply `AssignedPatientPermission` on record creation — records are only readable by the creating clinician, their department, or explicitly shared.

**12. No structured logging / log aggregation**
- No `LOGGING` dict found in `settings.py`. All Django log output goes to stdout/stderr with no structure, levels, or persistence. Audit logs in the database are good but operational logs need a separate path.
- Fix: Add a `LOGGING` configuration writing structured JSON to stdout (use `python-json-logger`). In production, ship logs to CloudWatch, Datadog, Loki, or equivalent. This is a compliance requirement — audit logs must be durable and tamper-evident beyond container restarts.

**13. CI pipeline uses fallback insecure keys**
- `ci.yml`: `SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY || 'django-insecure-ci-test-key' }}`. The `||` fallback means CI runs silently with insecure defaults if the GitHub secret is not set.
- Fix: Remove the fallback entirely. If the secret is not set, the workflow should fail loudly: `${{ secrets.DJANGO_SECRET_KEY }}` with no fallback.

**14. Celery Flower (task monitor) has no authentication**
- `docker-compose.yml` exposes Flower on port 5555 with no `--basic-auth` flag. Flower shows all task arguments which may include patient IDs and clinical context.
- Fix: Add `--basic-auth=user:${FLOWER_PASSWORD}` to the Flower command. Or put behind nginx basic auth.

**15. Celery task payloads may contain PHI**
- Tasks in `ai_tasks.py` and `appointment_tasks.py` pass clinical context through Redis (the broker) in plaintext.
- Fix: Pass only IDs through task arguments (never PHI). Fetch the data inside the task from the database. Configure Redis with `requirepass` and TLS (`rediss://`).

**16. WebSocket auth token passed as URL query parameter**
- `api/middleware/ws_auth.py` passes JWT as `?token=...` in the WebSocket URL. Query parameters are logged in web server access logs, proxies, and browser history.
- Fix: Use the WebSocket subprotocol header to pass the token, or implement a short-lived single-use ticket: `POST /ws/ticket` returns a one-time ticket UUID, which is then passed in the WebSocket URL and validated once.

---

## PART 4 — BACKEND / DATABASE ISSUES

**17. No database backup automation implemented**
- `docs/BACKUP_STRATEGY.md` describes the strategy but there's no actual implementation — no Celery task, no `pg_dump` wrapper, no S3 upload.
- Fix: Implement a Celery Beat task running `pg_dump | gzip | aws s3 cp` to an encrypted S3 bucket daily, hourly WAL shipping for PITR. Test restore quarterly. For a healthcare system, no backup = existential risk.

**18. No disaster recovery / failover configured**
- Single Postgres instance (Neon). No read replicas, no documented RTO/RPO.
- Fix: Configure Neon branching + PITR. Document RTO target (e.g. 4 hours) and RPO target (e.g. 1 hour). For a multi-hospital system, any DB outage means all hospitals lose record access simultaneously.

**19. No test coverage reporting in CI**
- CI runs `pytest` with no `--cov` flag. Coverage gaps are invisible across 73k lines of Python.
- Fix: Add `pytest --cov=. --cov-fail-under=70 --cov-report=xml` to CI. Upload to Codecov. Set 70% as the minimum floor; raise incrementally.

**20. Deploy steps in CI are echo stubs**
- `deploy-staging` and `deploy-production` jobs in `ci.yml` are `echo "Deploying..."`. Every production deployment is a manual, error-prone human step.
- Fix: Implement actual deployment automation. For Railway: `railway up`. For Vercel frontend + Railway backend: wire both with environment-specific secret injection from GitHub Secrets.

---

## PART 5 — CLINICAL MODEL GAPS

**21. No CarePlan / TreatmentPlan model**
- Every modern EMR and FHIR R4 requires a `CarePlan` resource. Without it, doctors can record diagnoses and prescriptions but cannot define a structured treatment goal, timeline, or multi-disciplinary care plan. The FHIR `$everything` bundle is incomplete without it.
- Fix: Add `CarePlan` model with: `patient`, `created_by`, `title`, `description`, `goals` (JSONField), `start_date`, `end_date`, `status`, `team_members` (M2M to User). Add FHIR serializer.

**22. No patient portal / self-service access layer**
- Zero patient-facing API or UI. Patients cannot view their own records, lab results, appointments, or consent status. Required by Ghana Digital Health Strategy 2023–2027, NDPA 2012 §25, and is standard in all modern EMR systems.
- Fix: Create a separate `patient_portal` Django app with its own authentication (phone number + OTP, not staff credentials). Minimum endpoints: `GET /portal/me`, `GET /portal/appointments`, `GET /portal/results`, `GET /portal/consents`, `POST /portal/consent/revoke`. Build a separate Next.js route group `(portal)` or a standalone app.

**23. Vital signs missing critical clinical scores**
- The `Vital` model has the 8 core vitals but is missing: Glasgow Coma Scale (GCS), AVPU score, pain score (0–10 NRS), and NEWS2 early warning score. All are standard in Ghanaian hospital triage and required for ICU and emergency ward types.
- Fix: Add `gcs_eye`, `gcs_verbal`, `gcs_motor`, `avpu_score`, `pain_score`, `news2_score` fields to the `Vital` model. Auto-calculate `news2_score` from the other vitals using a property or signal.

**24. No RadiologyOrder / ImagingStudy model**
- `radiology_technician` is a defined role with RBAC entries but there is no `RadiologyOrder` model. The FHIR `ImagingStudy` serializer is referenced in the FHIR views but the underlying data doesn't exist.
- Fix: Add `RadiologyOrder` model parallel to `LabOrder`: `test_type` (X-ray, ultrasound, CT, MRI, echo), `urgency`, `clinical_indication`, `ordering_doctor`, `assigned_technician`, `status`, `report` (encrypted text), `reported_at`. Add FHIR `ImagingStudy` serializer consuming it.

**25. No Medication Administration Record (MAR) write path**
- MAR views exist (`mar_views.py`) but there's no `MedicationAdministration` model in `records/models.py`. The actual nursing action of giving a dose has no persistent record — a serious patient safety gap and a HIPAA audit trail requirement.
- Fix: Add `MedicationAdministration` model: `prescription` (FK), `administered_by` (nurse FK), `administered_at`, `dose_given`, `route`, `site`, `notes`, `refused` (bool), `refused_reason`. This populates the MAR chart (`MarChart.tsx` already exists in the frontend).

**26. No FamilyHistory model**
- No `FamilyMemberHistory` model (FHIR resource). Essential for AI risk prediction models which claim to predict chronic disease risk — family history is a primary predictor for diabetes, hypertension, and sickle cell disease (highly relevant in Ghana).
- Fix: Add `FamilyHistory` model: `patient`, `relationship` (parent/sibling/grandparent/child), `condition`, `icd10_code`, `age_of_onset`, `deceased` (bool), `notes`. Add to FHIR `$everything` bundle.

**27. No DHIMS-2 export / reporting module**
- Ghana Health Service mandates monthly DHIMS-2 indicator reporting from all registered facilities. The system has the data (diagnoses, lab results, admissions) but no aggregation or export layer.
- Fix: Create a `dhims2` Django app. Implement: `DHIMS2Report` model (facility, period, indicators JSONField, submitted_at, status), a Celery task that aggregates monthly indicators from the clinical data, and a submission client for the DHIMS-2 API. Wire a Celery Beat schedule for the 5th of each month.

**28. NHIS integration is a stub**
- The `NHISClient` is well-designed but `NHIS_API_BASE_URL=https://api.nhia.gov.gh/v2` is a placeholder. Real NHIA registration, G-DRG coding, and claim validation against the NHIA approved drug/procedure list are all missing.
- Fix: Register with NHIA for facility API access. Implement: G-DRG code lookup table, NHIA approved drug formulary check (validate prescription drug names against it before claim submission), claim line item validation before `submit_claim()`.

**29. No Social Determinants of Health (SDOH) model**
- For Ghana specifically: occupation, education level, water access, sanitation, distance to nearest facility, and insurance status are major health determinants. The AI models reference `nhis_access_score` but there's no structured SDOH model.
- Fix: Add `SocialHistory` model: `patient`, `occupation`, `education_level`, `water_source`, `sanitation`, `distance_to_facility_km`, `nhis_enrolled`, `nhis_card_valid`, `household_size`. Feed into AI feature engineering.

**30. Consent scope needs granular resource-level control**
- Consent is currently binary: `SUMMARY` or `FULL_RECORD`. Real-world consent should be resource-specific — a patient may consent to sharing diagnoses but not mental health notes or HIV status.
- Fix: Add `ConsentScopeExclusion` model (M2M on `Consent`): `resource_type` (choices: mental_health, hiv_status, reproductive_health, substance_use), `excluded` (bool). Update `_can_access_patient_fhir()` to filter excluded resource types from the bundle. Align with FHIR `Consent` resource provisions.

**31. No notifiable disease automated reporting**
- `MedicalRecord` has a `notifiable_disease` type but there's no automated reporting pipeline to the Ghana Public Health Division (PHD). Notifiable diseases (cholera, typhoid, meningitis, etc.) legally require immediate reporting.
- Fix: Add a Django signal on `MedicalRecord.save()` that triggers a Celery task when `record_type == 'notifiable_disease'`. Task should: create a structured report, email the GHS District Health Office, and log the submission in an audit entry.

**32. No record retention period enforcement**
- Ghana MoH requires clinical records retention for a minimum of 10 years (adult) and 25 years (paediatric from age of majority). Records can currently be soft-deleted at any time.
- Fix: Add `retention_until` calculated field to `MedicalRecord` (set on creation based on patient age). Add a guard in all soft-delete views: `if record.retention_until > timezone.now(): raise ValidationError("Record cannot be deleted — legal retention period active")`.

**33. No medication reconciliation workflow**
- At admission and discharge, comparing home medications vs prescribed medications (medication reconciliation) is a mandated patient safety step. No screen or workflow exists.
- Fix: Add `MedicationReconciliation` model: `patient`, `encounter`, `type` (admission/discharge), `completed_by`, `completed_at`, `home_medications` (JSONField list), `discrepancies` (JSONField), `action_taken`. Trigger at admission event creation and encounter close.

---

## PART 6 — ARCHITECTURE GAPS

**34. No API versioning strategy**
- All routes use `/api/v1/` but there's no DRF versioning class, no version negotiation, and no deprecation policy. Breaking changes will affect all hospitals simultaneously.
- Fix: Add `DEFAULT_VERSIONING_CLASS = 'rest_framework.versioning.URLPathVersioning'` to DRF settings. Move routes to `/api/v1/`. Document a deprecation policy: minimum 6 months notice + parallel support for old version.

**35. No inter-hospital API trust model**
- The interop layer assumes all hospitals share one MedSync instance. In a real network, different hospitals may run separate instances. There's no mutual TLS, no service account tokens, and no federation protocol.
- Fix: Define the trust boundary: Option A (single-instance, current) — document that all hospitals must use the central MedSync instance. Option B (federated) — implement OAuth2 client credentials flow between instances, with a central trust registry.

**36. No circuit breaker for Postgres or Redis**
- `CircuitBreaker` exists for push notifications and the NHIS client but not for the database or Redis connections.
- Fix: Add connection pool limits (`CONN_MAX_AGE`, `pool_size`) to the Django database config. Add a circuit breaker wrapper around Redis operations in the CDS engine that degrades to DB fallback on Redis unavailability.

**37. Offline sync conflict resolution has no UI or strategy**
- `offline-store.ts` tracks `status: 'conflict'` when two offline writes clash. No UI for resolution exists anywhere in the codebase. For clinical data, last-write-wins is dangerous.
- Fix: Add a `ConflictResolutionScreen` that shows both versions side by side with field-level diff highlighting. Default to "newer wins" for vitals, "require manual resolution" for diagnoses and prescriptions. Backend: add `conflict_resolution_required` flag to sync endpoint response.

**38. No rate limiting on FHIR endpoints**
- FHIR views have `IsAuthenticated` but no `throttle_classes`. The `$everything` bundle assembly is an expensive multi-table query.
- Fix: Add `throttle_classes = [FHIRScopedThrottle]` to all FHIR views with a dedicated FHIR throttle rate (e.g. `fhir: 60/minute` per authenticated user). Add a separate rate for the `$everything` endpoint (e.g. `fhir_everything: 10/minute`).

---

## PART 7 — THINGS TO REMOVE / CLEAN UP

**39. Test artefacts committed to repo**
- `medsync-frontend/test-results/` (6.2 MB) and `playwright-report/` are committed. They're in `.gitignore` now but the existing committed versions remain in git history.
- Fix: `git rm -r --cached medsync-frontend/test-results medsync-frontend/playwright-report` then commit.

**40. Test output text files with Windows paths**
- `medsync-backend/full_test_results.txt`, `test_output.txt`, `test_results.txt` are committed and contain local machine paths (`C:\Users\OSCARPACK\...`).
- Fix: Delete these files. Add `*.txt` test output to `.gitignore` in the backend directory.

**41. One-off debugging scripts at project root**
- `mfa_diagnostic.py`, `check_mfa.py`, `activate_mfa.py`, `grant_admin_access.py`, `check_emergency_fields.py`, `check_time_sync.py` are one-off debug scripts at the project root.
- Fix: Move to `scripts/dev/` and gitignore in production, or convert to proper Django management commands under `management/commands/`.

**42. SETUP_COMPLETE.txt should not be committed**
- Developer scratchpad with no value in a shared repo.
- Fix: Delete and add to `.gitignore`.

**43. Empty synthea directories at repo root**
- `/synthea` and `/synthea-international` appear to be empty placeholder or stale submodule directories.
- Fix: If synthetic data is handled internally by `ml/generate_demo_patients.py`, remove these directories. They confuse anyone new to the codebase about the data pipeline.

**44. `README.md` claims "100/100 production readiness"**
- This will erode trust with technical reviewers, MoH evaluators, or hospital IT administrators reviewing the system.
- Fix: Replace with an honest status matrix: feature completeness (%), known gaps, deployment checklist. A realistic README builds more credibility than a perfect score.

---

## PART 8 — UI / UX ISSUES

### Navigation & layout

**45. Sidebar has no collapsible section grouping**
- Doctor has 8+ nav items, super_admin has 12+, all stacking vertically with no grouping.
- Fix: Add accordion-style section groups: "Clinical" (worklist, encounters, AI), "Patients" (search, admissions, alerts), "Admin" (staff, audit, reports). Mirror Epic's orbit menu pattern. In collapsed sidebar mode, groups show as icon clusters.

**46. Command palette doesn't search patients inline**
- `CommandPalette.tsx` has hardcoded navigation commands only. The highest-frequency EMR action — finding a patient — requires navigating away to `/patients/search`.
- Fix: Wire the command palette to `GET /api/v1/patients/?search=<query>` with debounce. Results show: full name, Ghana Health ID, DOB, registered hospital. Selecting opens the patient detail page. Show most-recently-viewed patients when the palette opens with no query.

**47. Doctor dashboard live update is invisible**
- The 60-second poll shows a small grey "Last refreshed HH:MM" text. Doctors don't look at it.
- Fix: Add a subtle pulse animation on worklist rows when new encounters arrive via WebSocket. Show an unread badge count on the worklist nav item. Add a small green dot that blinks for 3 seconds after a refresh brings new data.

**48. No persistent global patient context banner across pages**
- `PatientContextBanner.tsx` exists in the layout folder but isn't applied globally. When a doctor navigates from the patient detail page to the Lab or Pharmacy section, patient context is lost.
- Fix: When a patient is "active" (the doctor opened them), mount a sticky 36px top-bar strip showing: patient name, Ghana Health ID, DOB, blood group, allergy flag (red if active). This strip persists until the doctor explicitly closes it. Prevents wrong-patient errors.

**49. Breadcrumbs not applied consistently**
- `breadcrumbs.tsx` exists but isn't used on deep pages like `/patients/[id]/encounter/[eid]/vitals`.
- Fix: Add `<Breadcrumbs items={[{label:'Patients', href:'/patients'}, {label:patientName, href:`/patients/${id}`}, {label:'Vitals'}]} />` in the `[id]` patient layout as a standard wrapper.

### Patient detail page

**50. Patient page has 11 tabs — cognitive overload**
- Tabs: overview, encounters, diagnoses, prescriptions, labs, vitals, amendments, ai_history, ai_analysis, timeline, mar.
- Fix: Collapse to 5–6 logical groups: "Summary" (overview + timeline), "Clinical Record" (diagnoses + prescriptions + vitals + mar), "Diagnostics" (labs + radiology), "Amendments" (amendments log), "AI" (ai_history + ai_analysis), "Interop" (consents + referrals). Use progressive disclosure inside each group.

**51. No patient photo / identifying visual**
- Ward nurses managing 20+ patients have no visual identifier per patient card or bed.
- Fix: Add `photo_url` field to `Patient` model (stored in S3, served via signed URL). At registration, offer a webcam/phone camera capture. If no photo, generate a deterministic avatar using initials + blood group colour. Research shows visual patient identifiers reduce medication errors by 12–15%.

**52. No wristband print button post-admission**
- `PrintableMedicalRecord.tsx` exists but no wristband print layout.
- Fix: Add a "Print wristband" button on the admission confirmation screen. 80×20mm thermal-print layout: patient name, DOB, Ghana Health ID, blood group, allergy flag, barcode (Code 128 encoding the patient UUID). Use browser `window.print()` with a `@media print` stylesheet.

**53. No "clinical flag" / important notes feature**
- Critical non-coded patient notes ("Patient is Jehovah's Witness — no blood products", "Interpreter required", "Latex allergy not in system") have no home.
- Fix: Add `ClinicalFlag` model: `patient`, `flag_text`, `severity` (info/warning/critical), `visibility` (ward_only/all_staff/inter_hospital), `created_by`, `created_at`, `expires_at`. Display prominently at the top of the patient header in red/amber/blue based on severity.

### Forms & data entry

**54. Vital signs form has no real-time normal range feedback**
- Entering BP 190/120 produces no immediate warning.
- Fix: Add inline colour-coded range indicators next to each vital input that update on `onChange`. Thresholds: temperature (>38°C = amber, >39.5°C = red), BP systolic (>140 = amber, >180 = red), SpO2 (<94% = amber, <90% = red). Auto-calculate and display NEWS2 score below the form updating in real time. Show "Critical — escalate immediately" if NEWS2 ≥ 7.

**55. Autosave state on encounter form not clearly visible**
- `auto-save-indicator.tsx` and `use-encounter-auto-save.ts` exist but it's unclear the indicator is wired to the main SOAP form.
- Fix: Make autosave state explicit: animated spinner → "Saving..." → "Saved 12s ago" → yellow dot "Unsaved changes". Place it next to the encounter title, always visible. Doctors must trust their notes survive a refresh.

**56. No voice-to-text / dictation for clinical notes**
- Clinical notes (SOAP format) are the highest-friction data entry task for doctors.
- Fix: Add a microphone button to all `textarea` clinical note fields. Use the Web Speech API (no backend required). On click: start recording, transcribe in real time into the textarea, show a waveform animation. Add a "Stop" button. Test with Ghanaian English accent patterns. This alone could reduce note entry time by 60%.

**57. No smart drug search / autocomplete in prescription form**
- Drug name is a plain text input. Allows inconsistent naming ("Amoxil" vs "amoxicillin 250mg") which breaks drug interaction detection.
- Fix: Replace the drug name input with a `SearchableSelect` (component already exists) backed by `GET /api/v1/pharmacy/stock/search?q=<query>`. Results show: drug name, strength, form, available quantity, NHIA formulary status. Selecting auto-fills drug name and enables dose validation.

---

## PART 9 — AI / ML GAPS

**58. No AI-assisted SOAP note generation**
- The LLM client does differential diagnosis but doesn't assist with note writing. This is the single highest-ROI AI feature in clinical practice.
- Fix: Add a "Generate SOAP" button on the encounter form. Send the doctor's free-text history to the LLM with a structured prompt: "Extract and structure as SOAP: Chief Complaint, HPI, ROS, Physical Exam, Assessment, Plan. Return JSON." Pre-populate form fields from the response. Doctor reviews and edits before saving.

**59. Differential diagnosis is isolated from the encounter workflow**
- AI differential lives on a separate page requiring navigation away from the patient.
- Fix: Add a collapsible `DifferentialPanel` inside the SOAP encounter form, triggered automatically when the doctor finishes the Assessment field (on blur/tab). Shows top 5 differentials with confidence %, ICD-10 codes, and "Add to diagnoses" buttons. Zero context switches.

**60. No predictive vitals deterioration alert**
- Vitals are tracked over time but there's no trend-based early warning.
- Fix: Add a Celery Beat task running every 30 minutes that: calculates NEWS2 trend slope for each admitted patient over the last 6 hours, flags patients with upward trend (slope > threshold), creates a `ClinicalAlert` with severity based on NEWS2 trajectory. Push WebSocket alert to the nurse assigned to that ward.

**61. No AI prescription dose validation at point of prescribing**
- CDS checks drug-drug interactions but not dose appropriateness for the specific patient.
- Fix: When a prescription is saved, call a CDS rule (or LLM prompt) that checks: dose against patient weight and renal function (use creatinine from latest labs if available), frequency against severity of condition, duration against Ghana NDF/BNF guidelines. Surface as an inline warning before the prescription is confirmed.

**62. AI risk scores have no explainability (XAI)**
- `RiskScoresWidget.tsx` shows risk scores as numbers (e.g. "78% readmission risk") with no explanation.
- Fix: Add SHAP value computation to the ML inference pipeline. Return top 5 feature contributions with the score. Render as a small horizontal bar chart under each score: "Readmission 78% — Age 67 (+15%), 3 prior admissions (+22%), uncontrolled HbA1c (+18%), malaria episode 3mo ago (+12%), no follow-up appointment (-7%)". Without this, clinicians won't trust or act on AI scores.

**63. No AI-powered ICD-10 code suggestion**
- Doctors must type ICD-10 codes manually. This leads to miscoding, billing rejections, and NHIS claim failures.
- Fix: After the doctor writes the Assessment section, call the LLM with a prompt to extract conditions and suggest ICD-10 codes. Show a suggestion panel: "Suggested codes: E11.65 (Type 2 diabetes with hyperglycaemia) — Add, J18.9 (Pneumonia, unspecified) — Add". Greatly improves billing accuracy and NHIS claim acceptance.

**64. ML models trained on non-Ghana data — domain shift risk**
- `datasets.py` pulls from Kaggle US hospital datasets. Ghana's disease burden (malaria, typhoid, sickle cell, TB, sepsis) is fundamentally different from US data. Models trained on US datasets will perform poorly in Accra hospitals.
- Fix: Implement a model performance monitoring dashboard (`model_monitor.py` already exists). Set alert thresholds for AUC drop > 5% month-over-month. Design a feedback loop: when doctors correct an AI prediction, store the correction as a labelled training example. Schedule quarterly model retraining using accumulated real-world data.

**65. No clinician feedback / correction loop for AI outputs**
- When a doctor disagrees with an AI differential or risk score, there's nowhere to record the disagreement.
- Fix: Add thumbs-up / thumbs-down buttons on every AI output. On thumbs-down, show a correction form: "The correct diagnosis was: [input]" or "The risk level was: [low/medium/high]". Store corrections in an `AIFeedback` model. These become labelled training data and are required for any responsible clinical AI deployment.

**66. Similar patients feature shows identifiable patient names**
- `SimilarPatients.tsx` shows patient names in the cohort. This is a privacy violation for patients who haven't consented to being shown to other doctors.
- Fix: Anonymise similar patient display: "3 similar patients: 67yo male, T2DM + HTN, 2 prior admissions — 2 recovered on current plan, 1 required ICU escalation." Only show names if the viewing doctor has active consent for those patients.

**67. No AI performance / adoption dashboard for admins**
- `admin_ai_views.py` exists but no frontend consumes it.
- Fix: Build an "AI Performance" section in the hospital admin dashboard showing: AI consultation rate (% encounters where AI was used), agreement rate (% AI diagnoses confirmed by doctor), average time saved per consultation, model accuracy trend, feature importance chart, per-role usage breakdown.

---

## PART 10 — CLINICAL WORKFLOW ISSUES

**68. SBAR handover screen referenced but doesn't exist**
- `SbarHandoverReport.tsx` is referenced in imports but the file doesn't exist in `components/features/`. SBAR is the Ghana MoH-mandated nursing handover standard.
- Fix: Build `SbarHandoverReport.tsx`: a structured form with four sections (Situation, Background, Assessment, Recommendation), pre-populated from the patient's current admission data. Generates a printable handover report. Accessible from the ward dashboard at shift end.

**69. Queue board referenced but doesn't exist**
- `QueueBoard.tsx` is referenced but doesn't exist.
- Fix: Build a `/queue-board` route with a full-screen display mode (no navigation chrome). Shows: "Now serving: B003 — Room 2". Auto-cycles through the queue with configurable display duration. No authentication required (public display mode). Receptionist manages the queue from their dashboard; the board reflects it in real time via WebSocket.

**70. No escalation / rapid response workflow**
- When a patient deteriorates, there's no in-system way to trigger a rapid response team call or alert the on-call doctor. Alerts are passive (they appear on dashboards).
- Fix: Add an "Escalate" button on each bed card that: creates a `RapidResponseEvent` record with timestamp, sends a WebSocket push to the on-call doctor for that ward, sends an SMS via Africa's Talking to the doctor's registered phone, requires acknowledgement within 5 minutes with a countdown visible to the nurse.

**71. No digital consent form capture**
- Informed consent for procedures and inter-hospital data sharing currently has no patient-signed record in the system.
- Fix: Add a `ConsentForm` model: `consent_type` (procedure, data_sharing, hiv_test, operation), `patient_signature` (base64 PNG or typed name), `witness_signature`, `signed_at`, `ip_address`. Add a signature pad widget to the patient detail page using a canvas element. Generate a signed PDF receipt.

**72. Lab critical values have no auto-escalation**
- When a critical lab result is entered (e.g. K+ 6.8 mmol/L, Hb 4.2 g/dL), the system takes no immediate action beyond adding it to the worklist.
- Fix: Add a `CRITICAL_VALUE_THRESHOLDS` configuration dict per test type. On `LabResult.save()`, check if value crosses the critical threshold. If yes: mark the `LabOrder` status as `CRITICAL`, create a high-severity `ClinicalAlert`, send a WebSocket push to the ordering doctor, require acknowledgement with a reason field within a configurable time window.

**73. Pharmacy queue shows no estimated wait time**
- `PendingDispensePanel.tsx` shows a list of pending prescriptions with no wait time estimate.
- Fix: Calculate estimated wait time from: queue position × average dispense time (track this as a running average per pharmacy). Show "Est. wait: 14 minutes" on the patient-facing queue board and in the pending prescription view.

**74. No drug expiry proactive alert**
- Pharmacy stock has expiry dates but no proactive alerts.
- Fix: Add a Celery Beat task running daily that queries `PharmacyStock.objects.filter(expiry_date__lte=now()+timedelta(days=90))`. Create alerts and email the pharmacy manager weekly with a formatted expiry report. Highlight expiring items in red on the stock dashboard.

---

## PART 11 — MOBILE / PWA ISSUES

**75. Bottom nav doesn't cover lab_technician or pharmacy_technician roles**
- `BottomNav.tsx` handles 5 roles but `lab_technician` and `pharmacy_technician` fall through to a generic nav. These are high-mobile-usage roles.
- Fix: Add role-specific nav sets: lab_technician: [Dashboard, Lab Orders, Pending Results, Alerts]; pharmacy_technician: [Dashboard, Dispense Queue, Stock, Alerts].

**76. Bed grid is unusable on mobile**
- `BedGrid.tsx` uses `xl:grid-cols-5`. On a phone, each bed card collapses to full width, creating a long vertical scroll.
- Fix: On mobile (`< md` breakpoint), switch to a horizontally scrolling row grouped by ward section. Each bed = a compact 80px × 60px colour-coded tile showing bed code + patient initials + a vitals status dot. Tap to expand into a bottom sheet with full bed details.

**77. No barcode / QR scanner integration**
- The PWA has camera access but no barcode/QR scanning.
- Fix: Add a `BarcodeScanner` component using the browser's `BarcodeDetector` API (with ZXing fallback). Two use cases: (1) Nurse scans patient wristband QR → opens patient record immediately, bypassing search. (2) Pharmacist scans drug barcode before dispensing → system verifies against the prescription (5 rights check: right patient, drug, dose, route, time). This is one of the highest-value mobile features possible.

**78. No push notification implementation**
- Service worker and `ServiceWorkerRegistration.tsx` exist but there's no push notification subscription or display logic. `push_notification_circuit` exists in the backend but is never triggered to the frontend.
- Fix: Implement Web Push: `POST /api/v1/push/subscribe` stores the push subscription. Backend triggers notifications for: critical lab results, new admissions to nurse's ward, break-glass access alerts, incoming referrals. Use `web-push` Python library on the backend.

**79. No step-up biometric re-authentication for high-risk actions**
- On mobile, entering a password to confirm a "break-glass access" or "cancel prescription" is slow. WebAuthn (already implemented for passkeys) supports step-up authentication.
- Fix: For actions tagged `high_risk` (break-glass, prescription cancellation, record amendment, role change), trigger a `navigator.credentials.get()` challenge requiring biometric confirmation before the API call proceeds. No full re-login required.

**80. Offline conflict resolution UI is completely absent**
- `offline-store.ts` sets `status: 'conflict'` but no resolution UI exists. In a low-connectivity ward environment, conflicts will be common.
- Fix: Add a `ConflictResolutionQueue` component accessible from the sync status indicator. Shows conflicting records side-by-side with field-level diff. Options: "Keep mine", "Keep server version", "Merge manually". Audit log the resolution choice with the clinician's ID.

---

## PART 12 — MISSING FEATURES (scope additions)

**81. No telemedicine / remote consultation**
- Ghana Digital Health Strategy 2023–2027 explicitly targets telehealth. For inter-hospital access specifically (your core brief), referring doctors should be able to initiate a video call with a specialist at another hospital alongside the shared patient record.
- Fix: Integrate WebRTC using Daily.co or 100ms (both have HIPAA-compliant plans). Add a "Start video consultation" button on the referral detail page. The call is scoped to the referral — both participants must have valid consent for that patient. Record call metadata (start, end, participants) in a `Teleconsultation` model.

**82. No patient SMS appointment reminders**
- Ghanaian outpatient no-show rate is ~35% without reminders. You have the appointment model and email tasks.
- Fix: Integrate Africa's Talking or Hubtel SMS API (both operate in Ghana). Send: appointment confirmation SMS on booking, reminder 24 hours before, reminder 2 hours before. Allow patients to reply "CANCEL" or "CONFIRM". Track response in appointment status.

**83. No hospital operations analytics dashboard**
- Hospital admins have audit logs and RBAC review but no operational metrics.
- Fix: Build an analytics section in the admin dashboard using Recharts (already a frontend dependency). Metrics: bed occupancy rate (by ward), average length of stay (by diagnosis category), lab turnaround time (ordered → resulted), prescription-to-dispense time, appointment no-show rate, revenue per service line (from billing data), daily/weekly/monthly patient volume trends.

**84. No secure inter-hospital provider messaging**
- Referral records exist but doctors often need to discuss cases. Currently they use personal phones.
- Fix: Add a `Message` model: `thread` (FK, tied to a referral or patient record), `sender` (User FK), `recipient` (User FK), `hospital_sender`, `hospital_recipient`, `content` (encrypted), `sent_at`, `read_at`. Build a messaging UI in the referral detail page. All messages are scoped to the patient record and auditable. Push via WebSocket (already implemented).

**85. Medical certificate PDF generation**
- `MedicalCertificateForm.tsx` exists but likely doesn't generate a verifiable PDF.
- Fix: Generate a PDF with: doctor name, GMDC licence number, hospital name + stamp (logo), patient name, diagnosis (ICD-10), fitness assessment, recommended rest period, issue date, QR code that links to a verification endpoint (`GET /api/v1/certificates/verify/<uuid>`). Use `reportlab` or `weasyprint` on the backend.

**86. No patient flow / wait time analytics**
- Every step has a timestamp: check-in → doctor seen → lab ordered → result → prescription → dispensed.
- Fix: Add a "Patient flow" view in the hospital admin section. Show a funnel chart of average time at each step. Surface the top 3 bottlenecks. "Average time from check-in to doctor: 47 minutes" is the kind of data that gets systems adopted by hospital management and justifies the investment.

**87. No generalised inventory / supply chain module**
- Pharmacy stock is well-modelled. But hospitals also manage ward consumables, lab reagents, surgical supplies, blood bank inventory.
- Fix: Generalise the pharmacy stock model into a `InventoryItem` model with `category` (pharmacy/consumable/reagent/blood_product/surgical). Reuse the stock-in, stock-out, reorder threshold logic. This evolves the system from EMR to full Hospital Information System (HIS).

**88. No real-time public health surveillance export**
- The system accumulates anonymised population-level data (disease incidence by region, age, sex, NHIS status) that is valuable for GHS surveillance.
- Fix: Add an anonymised aggregate export endpoint for public health use: `GET /api/v1/surveillance/export?period=monthly&region=greater_accra`. Returns: disease incidence counts by ICD-10 chapter, age group, sex — no individual patient data. This creates a pathway to align with the Ghana Health Data Ecosystem and positions the system as national infrastructure.

---

## PART 13 — POLISH & PERFORMANCE

**89. Dark mode is inconsistently applied**
- `DoctorDashboard.tsx` has only 7 `dark:` Tailwind classes in 400+ lines. Many components use hardcoded `bg-white`, `text-slate-900`, `border-slate-200` without dark variants. `globals.css` has the right CSS variables but they're not used everywhere.
- Fix: Audit all components for hardcoded light-mode colours. Either standardise on `var(--gray-900)` / `var(--teal-400)` CSS variables throughout, or migrate fully to Tailwind's `dark:` variant system. Pick one approach and enforce it.

**90. `ReferralSuggestions.tsx` uses raw Tailwind colours, not CSS variables**
- Uses `bg-white`, `border-gray-200`, `text-gray-900` — doesn't theme correctly in dark mode.
- Fix: Replace with `var(--background)`, `var(--border)`, `var(--gray-900)` from the CSS variable system. Audit all files in `components/features/ai/` and `components/features/clinical/` for the same issue.

**91. No skeleton loaders on several high-latency pages**
- The patient detail page shows a blank white area while loading. The AI insights page shows nothing while fetching recent patients.
- Fix: Apply `TimelineSkeletonLoader` (already exists in `/ui`) to every async-loaded section. No section should be blank — every loading state should have a recognisable placeholder layout.

**92. No keyboard shortcut reference / help overlay**
- The command palette has shortcuts (⌘P) but they're not discoverable.
- Fix: Add a `?` keyboard shortcut that opens a `KeyboardShortcutsModal` listing all shortcuts by role. Include a "Keyboard shortcuts" link in the user menu dropdown. Clinical staff who use the system 8 hours/day will learn shortcuts if they know they exist.

**93. `OnboardingTour.tsx` is not wired to first-login**
- The component exists but isn't triggered anywhere.
- Fix: Check `user.activated_at` on first dashboard load. If `activated_at` is within the last 24 hours, automatically launch the onboarding tour for the user's role. Tour should be role-specific: doctors get a 5-step tour of worklist → patient → encounter → AI; nurses get a tour of ward → bed grid → vitals → MAR.

**94. Empty states are generic, not actionable**
- Most empty states say "No results found." which provides no next action.
- Fix: Make every empty state contextual and actionable: "No lab orders for this patient — [Order a test ↗]", "No prescriptions today — [Write prescription ↗]", "No admissions this ward — [Admit a patient ↗]". Wire the CTA buttons to the correct action routes.

**95. i18n / localisation is completely absent**
- All text is hardcoded English. Ghana has 11 official languages; patients reading consent forms, queue boards, and appointment confirmations may not be English-first readers.
- Fix: Add `next-intl` to the frontend. Start with two locales: `en` (English) and `tw` (Twi — Ghana's most widely spoken indigenous language). Prioritise patient-facing screens: queue board, appointment confirmation SMS, consent form. Add a language selector to the patient portal (when built) and the queue board display.

**96. Accessibility (a11y) needs a full audit**
- 81 aria attributes across 40+ UI component files is thin for a healthcare application. Critical gaps: the `BedGrid` drag-and-drop has no keyboard equivalent, `VitalsTrendChart` Recharts canvas has no alt text or accessible table fallback, `CommandPalette` doesn't announce results to screen readers.
- Fix: Run `axe-core` accessibility audit on every page. Target WCAG 2.1 AA compliance. Priority fixes: add `aria-live="polite"` to the command palette results region, add keyboard controls to BedGrid (Tab to navigate beds, Enter to open, arrow keys to move patient with confirmation), add a `<table>` fallback below each Recharts chart.

---

## PART 14 — GHANA-SPECIFIC REQUIREMENTS SUMMARY

**97. NDPA 2012 right-to-erasure workflow missing (§27)**
- No `DataDeletionRequest` model, no anonymisation pipeline. Clinical records have legal retention periods (10 years adult, 25 years paediatric) that complicate deletion — anonymisation is the correct approach.
- Fix: Add `DataDeletionRequest` model with status workflow (submitted → reviewed → approved → processed). On approval, anonymise: replace name/DOB/phone with `ANONYMISED_[UUID]`, nullify national_id/nhis_number/passport_number, retain clinical records for legal retention period.

**98. NDPA 2012 Data Subject Access Request (DSAR) missing (§25)**
- No mechanism for patients to request a copy of all their data within the legally required 21 days.
- Fix: Add `DataAccessRequest` model. Admin workflow to generate a structured export of all patient data (JSON + PDF). When patient portal is built, allow patients to self-request. Implement a 21-day SLA tracker with email reminders to the data controller.

**99. Ghana Cyber Security Authority (CSA) health sector requirements**
- Ghana's health sector is a Critical Information Infrastructure (CII) sector per the CSA. GHS published an Information Security Policy in 2024. The CSA has noted Ghana's health sector is "low in cybersecurity maturity."
- Fix: Conduct a formal security assessment against the CSA's health sector security baseline. Key additions: vulnerability scanning schedule, penetration test before go-live, incident response plan documentation, staff security awareness training records.

**100. Integration with Ghana's broader digital health ecosystem**
- The system operates in isolation from: Ghana Health ID (GHID) system, DHIMS-2 national reporting, the Ghana Electronic Health Record Interoperability Framework (GEHRIF), and the Africa CDC digital health roadmap.
- Fix: Map integration points: (1) Ghana Health ID verification API — validate `ghana_health_id` on patient registration. (2) DHIMS-2 monthly submission (see item 27). (3) GEHRIF interoperability — align FHIR profiles with any Ghana national FHIR implementation guide when published. (4) Consider joining the Ghana Health Service's digital health pilot programme.

---

## PRIORITY EXECUTION ORDER

### Immediate (before any real patient data enters the system)
1. Rotate compromised secrets (item 5)
2. Migrate anomaly detection to Redis (item 1)
3. Add Argon2 password hashing (item 2)
4. Add session idle timeout (item 3)
5. Add LLM production guard (item 4)
6. Restrict Django admin URL (item 10)
7. Add structured `LOGGING` configuration (item 12)

### Sprint 1 — Core clinical completeness
8. CarePlan model + FHIR resource (item 21)
9. RadiologyOrder model (item 24)
10. MAR write path (item 25)
11. FamilyHistory model (item 26)
12. Vital signs: GCS, AVPU, pain score, NEWS2 auto-calc (item 23)
13. Consent withdrawal fields + audit (item 7)
14. FHIR CapabilityStatement endpoint (item 6)

### Sprint 2 — Ghana regulatory compliance
15. DHIMS-2 export module (item 27)
16. NHIS G-DRG code support (item 28)
17. Notifiable disease auto-reporting (item 31)
18. Record retention enforcement (item 32)
19. NDPA DSAR workflow (item 98)
20. NDPA data deletion / anonymisation workflow (item 97)

### Sprint 3 — UX & clinical workflow
21. Command palette patient search (item 46)
22. Vital signs normal range inline feedback + NEWS2 (item 54)
23. Patient photo / avatar (item 52)
24. SBAR handover screen (item 68)
25. Queue board (item 69)
26. Lab critical value escalation (item 72)
27. Drug autocomplete in prescription form (item 57)
28. Patient 11-tab → 5-tab consolidation (item 50)

### Sprint 4 — AI/ML improvements
29. AI differential panel inline in encounter form (item 59)
30. AI SOAP note generation (item 58)
31. XAI / SHAP explanations for risk scores (item 62)
32. ICD-10 code suggestion (item 63)
33. Clinician AI feedback loop (item 65)
34. Similar patients anonymisation (item 66)
35. Predictive vitals deterioration alert (item 60)

### Sprint 5 — Mobile & PWA
36. Barcode / QR scanner (item 77)
37. Push notifications (item 78)
38. Mobile bed grid (item 76)
39. Offline conflict resolution UI (item 80)
40. Bottom nav for lab + pharmacy roles (item 75)

### Sprint 6 — Extended features
41. Patient portal (item 22)
42. Telemedicine / video consultation (item 81)
43. Inter-hospital provider messaging (item 84)
44. Hospital operations analytics (item 83)
45. Appointment SMS reminders (item 82)
46. Medical certificate PDF generation (item 85)
47. SDOH model (item 29)
48. Inventory module generalisation (item 87)
49. i18n / Twi localisation (item 95)
50. WCAG 2.1 AA accessibility audit + remediation (item 96)

### Ongoing
- Database backup automation (item 17)
- CI coverage reporting at 70%+ threshold (item 19)
- Implement actual deploy steps in CI (item 20)
- ML model Ghana-specific retraining plan (item 64)
- Remove committed test artefacts (items 39–43)
- Fix dark mode consistency (item 89)
- Wire onboarding tour to first login (item 93)

---

## QUICK-WIN CHANGES (under 1 day each)

| Change | File | Impact |
|---|---|---|
| Add `PASSWORD_HASHERS` with Argon2 | `settings.py` | Security |
| Remove fallback keys from CI | `ci.yml` | Security |
| Add `--basic-auth` to Flower | `docker-compose.yml` | Security |
| Wire `InactivityModal.tsx` to logout | `layout.tsx` | Compliance |
| Add `pytest --cov` flag | `ci.yml` | Quality |
| Add `LOGGING` dict | `settings.py` | Observability |
| `git rm` test artefacts | repo root | Cleanliness |
| Delete debug scripts at root | repo root | Cleanliness |
| Update README to honest status | `README.md` | Credibility |
| Wire `OnboardingTour` to `activated_at` | `DashboardLayoutClient.tsx` | UX |
| Add NEWS2 auto-calc to Vital model | `records/models.py` | Clinical safety |
| Add `withdrawn_at` to Consent model | `interop/models.py` | Compliance |
| Add `retention_until` to MedicalRecord | `records/models.py` | Compliance |
| Add `FHIR CapabilityStatement` stub | `api/views/fhir_views.py` | Interoperability |

---

*Total findings: 100 items across security (16), architecture (8), clinical models (13), Ghana compliance (5), remove/clean (6), UX/design (18), AI/ML (10), clinical workflows (7), mobile/PWA (6), missing features (8), polish (3)*
