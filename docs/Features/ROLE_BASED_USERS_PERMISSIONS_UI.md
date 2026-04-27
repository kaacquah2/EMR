# MedSync Role-Based Users, Permissions, and UI Access

Last updated: 2026-03-27  
Source of truth used:
- `medsync-backend/core/models.py` (role definitions)
- `medsync-backend/core/management/commands/setup_dev.py` (seed users)
- `medsync-backend/api/permissions.py` (`PERMISSION_MATRIX`, endpoint-level RBAC)
- `medsync-backend/api/permissions_helpers.py` (object-level access rules)
- `medsync-frontend/src/lib/navigation.ts` (role navigation + route access)
- `medsync-frontend/src/components/layout/Sidebar.tsx` (visible UI navigation)

---

## 1) System Roles (Authoritative)

The backend defines these application roles:
- `super_admin`
- `hospital_admin`
- `doctor`
- `nurse`
- `receptionist`
- `lab_technician`

---

## 2) Role-Based Users (Dev Seed Accounts)

From `setup_dev.py` (local development seed data):

| Role | Default Email |
|---|---|
| super_admin | admin@medsync.gh |
| doctor | doctor@medsync.gh |
| doctor | doctor2@medsync.gh |
| hospital_admin | hospital_admin@medsync.gh |
| nurse | nurse@medsync.gh |
| receptionist | receptionist@medsync.gh |
| lab_technician | lab_technician@medsync.gh |

Notes:
- These are local/dev seed users.
- MFA is enabled for seeded users.
- `super_admin` is granted access to all hospitals in dev setup.

---

## 3) UI Access by Role (Sidebar + Route Guard)

## `super_admin`
- Core sidebar:
  - `/superadmin` (Dashboard)
  - `/superadmin/hospitals`
  - `/superadmin/cross-facility-activity-log`
  - `/superadmin/audit-logs`
  - `/superadmin/user-management`
  - `/superadmin/break-glass-review`
  - `/superadmin/facilities`
  - `/superadmin/system-health`
  - `/superadmin/ai-integration`
  - `/referrals`
- Additional clinical nav when View-As hospital is active:
  - `/patients/search`
  - `/appointments`
  - `/admissions`
  - `/alerts`

## `hospital_admin`
- Sidebar:
  - `/dashboard`
  - `/patients/search`
  - `/appointments`
  - `/admissions`
  - `/alerts`
  - `/referrals`
  - `/admin/users`
  - `/admin/facilities`
  - `/admin/rbac-review`
  - `/admin/audit-logs`

## `doctor`
- Sidebar:
  - `/dashboard`
  - `/worklist`
  - `/ai-insights`
  - `/patients/search`
  - `/appointments`
  - `/alerts`
  - `/referrals`
- Route guard specifics:
  - Can access patient chart routes (`/patients/<uuid>` and clinical subflows).
  - Blocked from `/patients/register`.
  - Blocked from `/admissions` and patient admissions sub-route.

## `nurse`
- Sidebar:
  - `/dashboard`
  - `/worklist`
  - `/patients/search` (shown as “My Ward”)
  - `/appointments`
  - `/alerts`
  - `/admissions`

## `receptionist`
- Sidebar:
  - `/dashboard`
  - `/patients/search`
  - `/appointments`

## `lab_technician`
- Sidebar:
  - `/dashboard`
  - `/lab/orders`

---

## 4) API Permissions by Role (All Endpoints in RBAC Matrix)

### `super_admin` (165 endpoints)
- `admin/audit-logs`: GET
- `admin/beds`: POST
- `admin/beds/<pk>`: PATCH
- `admin/departments`: GET
- `admin/departments/create`: POST
- `admin/doctors`: GET
- `admin/duplicates`: GET
- `admin/duplicates/<pk>`: GET, PATCH
- `admin/duplicates/create`: POST
- `admin/lab-test-types`: GET
- `admin/lab-test-types/create`: POST
- `admin/lab-units`: GET
- `admin/lab-units/create`: POST
- `admin/password-resets`: GET
- `admin/rbac-review`: GET
- `admin/staff-onboarding`: GET
- `admin/users`: GET
- `admin/users/<pk>`: GET, PUT, PATCH
- `admin/users/<pk>/generate-reset-link`: POST
- `admin/users/<pk>/generate-temp-password`: POST
- `admin/users/<pk>/resend-invite`: POST
- `admin/users/<pk>/reset-mfa`: POST
- `admin/users/<pk>/role`: PATCH
- `admin/users/<pk>/send-password-reset`: POST
- `admin/users/bulk-import`: POST
- `admin/users/invite`: POST
- `admin/wards`: GET
- `admin/wards/<pk>`: PATCH
- `admin/wards/<pk>/beds`: GET
- `admin/wards/<pk>/beds/bulk`: POST
- `admin/wards/create`: POST
- `admin/wards/occupancy`: GET
- `admissions`: GET
- `admissions/<pk>/discharge`: POST
- `admissions/create`: POST
- `admissions/ward/<pk>`: GET
- `ai/analysis-history/<pk>`: GET
- `ai/analyze-patient/<pk>`: POST
- `ai/clinical-decision-support/<pk>`: POST
- `ai/find-similar-patients/<pk>`: POST
- `ai/referral-recommendation/<pk>`: POST
- `ai/risk-prediction/<pk>`: POST
- `ai/status`: GET
- `ai/triage/<pk>`: POST
- `alerts`: GET
- `appointments`: GET, POST
- `appointments/<pk>`: GET, PUT, PATCH
- `appointments/<pk>/check-in`: POST
- `appointments/<pk>/delete`: DELETE
- `appointments/<pk>/no-show`: POST
- `appointments/<pk>/reschedule`: POST
- `appointments/<pk>/unmark-no-show`: POST
- `appointments/check-availability`: GET
- `appointments/create`: POST
- `appointments/no-show-statistics`: GET
- `audit/export`: GET, POST
- `audit/global-logs`: GET
- `audit/validate-chain`: POST
- `billing/invoices`: GET, POST
- `billing/nhis-claim`: POST
- `break-glass`: POST
- `break-glass/list`: GET
- `consents`: POST
- `consents/<pk>`: PATCH
- `consents/list`: GET
- `cross-facility-records/<pk>`: GET
- `dashboard`: GET
- `dashboard/analytics`: GET
- `dashboard/metrics`: GET
- `doctor/favorites/prescriptions`: GET, POST
- `doctor/prescriptions/<pk>/refill`: POST
- `doctor/records/<pk>/amendment-history`: GET
- `facilities`: GET, POST
- `facilities/<pk>`: PATCH
- `facility-patients/link`: POST
- `fhir/Condition`: GET
- `fhir/Condition/<pk>`: GET
- `fhir/Encounter`: GET
- `fhir/Encounter/<pk>`: GET
- `fhir/MedicationRequest`: GET
- `fhir/MedicationRequest/<pk>`: GET
- `fhir/Observation`: GET
- `fhir/Observation/<pk>`: GET
- `fhir/Patient`: GET
- `fhir/Patient/<pk>`: GET
- `global-patients/search`: GET
- `hl7/adt`: GET
- `icd10/search`: GET
- `interop/fhir-push`: POST
- `lab/analytics/trends`: GET
- `lab/attachments/upload`: POST
- `lab/orders`: GET
- `lab/orders/<pk>`: GET, PATCH
- `lab/orders/<pk>/result`: POST
- `lab/results/bulk-submit`: POST
- `nurse/dashboard`: GET
- `nurse/handover/<pk>/acknowledge`: POST
- `nurse/overdue-vitals`: GET
- `nurse/shift/<pk>/handover`: POST
- `nurse/shift/break-toggle`: POST
- `nurse/shift/end`: POST
- `nurse/shift/start`: POST
- `nurse/worklist`: GET
- `patients/<pk>`: GET, PUT, PATCH
- `patients/<pk>/allergies`: GET
- `patients/<pk>/diagnoses`: GET
- `patients/<pk>/encounters`: GET, POST
- `patients/<pk>/encounters/<pk>`: GET, PATCH
- `patients/<pk>/encounters/<pk>/close`: POST
- `patients/<pk>/export-pdf`: GET
- `patients/<pk>/labs`: GET
- `patients/<pk>/prescriptions`: GET
- `patients/<pk>/records`: GET
- `patients/<pk>/vitals`: GET
- `patients/duplicate-check`: GET, POST
- `patients/search`: GET
- `records/<pk>/amend`: POST
- `records/allergy`: POST
- `records/diagnosis`: POST
- `records/drug-autocomplete`: GET
- `records/icd10-autocomplete`: GET
- `records/lab-order`: POST
- `records/nursing-note`: POST
- `records/prescription`: POST
- `records/prescription/<pk>/dispense`: PATCH, POST
- `records/prescription/<pk>/dispense-by-nurse`: POST
- `records/radiology-order`: POST
- `records/radiology-order/<pk>/attachment`: POST
- `records/vitals`: POST
- `records/vitals/batch`: POST
- `referrals`: POST
- `referrals/<pk>`: PATCH
- `referrals/incoming`: GET
- `reports/audit/export`: GET, POST
- `reports/patients/export`: POST
- `superadmin/audit-chain-integrity`: GET
- `superadmin/audit-chain-integrity/validate`: POST
- `superadmin/audit-logs`: GET
- `superadmin/break-glass`: GET
- `superadmin/break-glass-list-global`: GET
- `superadmin/break-glass/<pk>/flag-abuse`: POST
- `superadmin/break-glass/<pk>/review`: POST
- `superadmin/compliance-alerts`: GET
- `superadmin/cross-facility-activity`: GET
- `superadmin/dashboard-bundle`: GET
- `superadmin/gmdc-unverified`: GET
- `superadmin/grant-hospital-access`: POST
- `superadmin/hospital-onboarding`: GET
- `superadmin/hospital-onboarding-list`: GET
- `superadmin/hospitals`: GET, POST, PATCH
- `superadmin/hospitals/<pk>/bulk-import-staff`: POST
- `superadmin/hospitals/<pk>/connectivity`: GET
- `superadmin/onboard-hospital`: POST
- `superadmin/onboarding-dashboard`: GET
- `superadmin/password-resets/suspicious`: GET
- `superadmin/pending-admin-grants`: GET
- `superadmin/pending-hospital-admin-assignments`: GET
- `superadmin/system-health`: GET
- `superadmin/users/<pk>/force-password-reset`: POST
- `superadmin/users/<pk>/force-password-reset-initiate`: POST
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET
- `worklist`: GET
- `worklist/encounters`: GET

### `hospital_admin` (107 endpoints)
- `admin/audit-logs`: GET
- `admin/beds`: POST
- `admin/beds/<pk>`: PATCH
- `admin/departments`: GET
- `admin/departments/create`: POST
- `admin/doctors`: GET
- `admin/duplicates`: GET
- `admin/duplicates/<pk>`: GET, PATCH
- `admin/duplicates/create`: POST
- `admin/lab-test-types`: GET
- `admin/lab-test-types/create`: POST
- `admin/lab-units`: GET
- `admin/lab-units/create`: POST
- `admin/password-resets`: GET
- `admin/rbac-review`: GET
- `admin/staff-onboarding`: GET
- `admin/users`: GET
- `admin/users/<pk>`: GET, PUT, PATCH
- `admin/users/<pk>/generate-reset-link`: POST
- `admin/users/<pk>/generate-temp-password`: POST
- `admin/users/<pk>/resend-invite`: POST
- `admin/users/<pk>/reset-mfa`: POST
- `admin/users/<pk>/role`: PATCH
- `admin/users/<pk>/send-password-reset`: POST
- `admin/users/bulk-import`: POST
- `admin/users/invite`: POST
- `admin/wards`: GET
- `admin/wards/<pk>`: PATCH
- `admin/wards/<pk>/beds`: GET
- `admin/wards/<pk>/beds/bulk`: POST
- `admin/wards/create`: POST
- `admin/wards/occupancy`: GET
- `admissions`: GET
- `admissions/<pk>/discharge`: POST
- `admissions/create`: POST
- `admissions/ward/<pk>`: GET
- `ai/analyze-patient/<pk>`: POST
- `ai/referral-recommendation/<pk>`: POST
- `alerts`: GET
- `appointments`: GET, POST
- `appointments/<pk>`: GET, PUT, PATCH
- `appointments/<pk>/check-in`: POST
- `appointments/<pk>/delete`: DELETE
- `appointments/<pk>/no-show`: POST
- `appointments/<pk>/reschedule`: POST
- `appointments/<pk>/unmark-no-show`: POST
- `appointments/check-availability`: GET
- `appointments/create`: POST
- `appointments/no-show-statistics`: GET
- `audit/export`: GET, POST
- `billing/invoices`: GET, POST
- `billing/nhis-claim`: POST
- `break-glass`: POST
- `break-glass/list`: GET
- `consents`: POST
- `consents/<pk>`: PATCH
- `consents/list`: GET
- `cross-facility-records/<pk>`: GET
- `dashboard`: GET
- `dashboard/analytics`: GET
- `dashboard/metrics`: GET
- `facilities`: GET
- `facility-patients/link`: POST
- `fhir/Condition`: GET
- `fhir/Condition/<pk>`: GET
- `fhir/Encounter`: GET
- `fhir/Encounter/<pk>`: GET
- `fhir/MedicationRequest`: GET
- `fhir/MedicationRequest/<pk>`: GET
- `fhir/Observation`: GET
- `fhir/Observation/<pk>`: GET
- `fhir/Patient`: GET
- `fhir/Patient/<pk>`: GET
- `global-patients/search`: GET
- `hl7/adt`: GET
- `icd10/search`: GET
- `interop/fhir-push`: POST
- `lab/orders`: GET
- `nurse/dashboard`: GET
- `nurse/overdue-vitals`: GET
- `nurse/worklist`: GET
- `patients`: POST
- `patients/<pk>`: GET, PUT, PATCH
- `patients/<pk>/allergies`: GET
- `patients/<pk>/diagnoses`: GET
- `patients/<pk>/encounters`: GET, POST
- `patients/<pk>/encounters/<pk>`: GET, PATCH
- `patients/<pk>/encounters/<pk>/close`: POST
- `patients/<pk>/labs`: GET
- `patients/<pk>/prescriptions`: GET
- `patients/<pk>/records`: GET
- `patients/<pk>/vitals`: GET
- `patients/duplicate-check`: GET, POST
- `patients/search`: GET
- `records/drug-autocomplete`: GET
- `records/icd10-autocomplete`: GET
- `records/prescription/<pk>/dispense`: PATCH
- `referrals`: POST
- `referrals/<pk>`: PATCH
- `referrals/incoming`: GET
- `reports/audit/export`: GET, POST
- `reports/patients/export`: POST
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET
- `worklist`: GET
- `worklist/encounters`: GET

### `doctor` (75 endpoints)
- `admin/wards/occupancy`: GET
- `admissions`: GET
- `admissions/<pk>/discharge`: POST
- `admissions/create`: POST
- `admissions/ward/<pk>`: GET
- `ai/analysis-history/<pk>`: GET
- `ai/analyze-patient/<pk>`: POST
- `ai/clinical-decision-support/<pk>`: POST
- `ai/find-similar-patients/<pk>`: POST
- `ai/referral-recommendation/<pk>`: POST
- `ai/risk-prediction/<pk>`: POST
- `ai/triage/<pk>`: POST
- `alerts`: GET
- `alerts/<pk>/resolve`: PATCH
- `appointments`: GET, POST
- `appointments/check-availability`: GET
- `appointments/no-show-statistics`: GET
- `break-glass`: POST
- `break-glass/list`: GET
- `consents`: POST
- `consents/<pk>`: PATCH
- `consents/list`: GET
- `cross-facility-records/<pk>`: GET
- `dashboard`: GET
- `dashboard/metrics`: GET
- `doctor/favorites/prescriptions`: GET, POST
- `doctor/prescriptions/<pk>/refill`: POST
- `doctor/records/<pk>/amendment-history`: GET
- `facilities`: GET
- `facility-patients/link`: POST
- `fhir/Condition`: GET
- `fhir/Condition/<pk>`: GET
- `fhir/Encounter`: GET
- `fhir/Encounter/<pk>`: GET
- `fhir/MedicationRequest`: GET
- `fhir/MedicationRequest/<pk>`: GET
- `fhir/Observation`: GET
- `fhir/Observation/<pk>`: GET
- `fhir/Patient`: GET
- `fhir/Patient/<pk>`: GET
- `global-patients/search`: GET
- `icd10/search`: GET
- `lab/orders`: GET
- `patients`: POST
- `patients/<pk>`: GET
- `patients/<pk>/allergies`: GET
- `patients/<pk>/diagnoses`: GET
- `patients/<pk>/encounters`: GET, POST
- `patients/<pk>/encounters/<pk>`: GET, PATCH
- `patients/<pk>/encounters/<pk>/close`: POST
- `patients/<pk>/export-pdf`: GET
- `patients/<pk>/labs`: GET
- `patients/<pk>/prescriptions`: GET
- `patients/<pk>/records`: GET
- `patients/<pk>/vitals`: GET
- `patients/duplicate-check`: GET, POST
- `patients/search`: GET
- `records/<pk>/amend`: POST
- `records/allergy`: POST
- `records/diagnosis`: POST
- `records/drug-autocomplete`: GET
- `records/icd10-autocomplete`: GET
- `records/lab-order`: POST
- `records/prescription`: POST
- `records/prescription/<pk>/dispense`: PATCH
- `records/radiology-order`: POST
- `records/radiology-order/<pk>/attachment`: POST
- `referrals`: POST
- `referrals/<pk>`: PATCH
- `referrals/incoming`: GET
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET
- `worklist`: GET
- `worklist/encounters`: GET

### `nurse` (38 endpoints)
- `admin/wards/occupancy`: GET
- `admissions`: GET
- `admissions/ward/<pk>`: GET
- `ai/analysis-history/<pk>`: GET
- `ai/analyze-patient/<pk>`: POST
- `ai/risk-prediction/<pk>`: POST
- `ai/triage/<pk>`: POST
- `alerts`: GET
- `alerts/<pk>/resolve`: PATCH
- `dashboard`: GET
- `dashboard/metrics`: GET
- `nurse/dashboard`: GET
- `nurse/handover/<pk>/acknowledge`: POST
- `nurse/overdue-vitals`: GET
- `nurse/shift/<pk>/handover`: POST
- `nurse/shift/break-toggle`: POST
- `nurse/shift/end`: POST
- `nurse/shift/start`: POST
- `nurse/worklist`: GET
- `patients/<pk>`: GET
- `patients/<pk>/allergies`: GET
- `patients/<pk>/encounters`: GET
- `patients/<pk>/encounters/<pk>`: GET
- `patients/<pk>/prescriptions`: GET
- `patients/<pk>/records`: GET
- `patients/<pk>/vitals`: GET
- `patients/search`: GET
- `records/drug-autocomplete`: GET
- `records/nursing-note`: POST
- `records/prescription/<pk>/dispense`: POST
- `records/prescription/<pk>/dispense-by-nurse`: POST
- `records/vitals`: POST
- `records/vitals/batch`: POST
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET
- `worklist`: GET
- `worklist/encounters`: GET

### `receptionist` (17 endpoints)
- `appointments`: GET, POST
- `appointments/<pk>`: GET, PUT, PATCH
- `appointments/<pk>/check-in`: POST
- `appointments/<pk>/delete`: DELETE
- `appointments/<pk>/no-show`: POST
- `appointments/<pk>/reschedule`: POST
- `appointments/<pk>/unmark-no-show`: POST
- `appointments/check-availability`: GET
- `appointments/create`: POST
- `appointments/no-show-statistics`: GET
- `dashboard`: GET
- `dashboard/metrics`: GET
- `patients/<pk>`: GET
- `patients/search`: GET
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET

### `lab_technician` (16 endpoints)
- `alerts`: GET
- `dashboard`: GET
- `dashboard/metrics`: GET
- `lab/analytics/trends`: GET
- `lab/attachments/upload`: POST
- `lab/orders`: GET
- `lab/orders/<pk>`: GET, PATCH
- `lab/orders/<pk>/result`: POST
- `lab/results/bulk-submit`: POST
- `patients/<pk>`: GET
- `patients/<pk>/labs`: GET
- `patients/duplicate-check`: GET, POST
- `patients/search`: GET
- `tasks`: GET
- `tasks/<pk>`: GET
- `tasks/<pk>/result`: GET

---

## 5) Object-Level / Scope Rules (Important)

Even when endpoint RBAC allows access, object-level checks enforce additional limits:

- `super_admin`: broad access; can operate globally (with optional view-as context).
- `doctor`:
  - Patient/encounter/record access is hospital-scoped.
  - Encounter access constrained to assigned doctor or assigned department.
- `nurse`:
  - Patient and record visibility constrained to currently admitted patients in nurse ward.
  - Encounter visibility constrained to nurse ward.
  - Admission updates limited to own ward.
- `hospital_admin`:
  - Scoped to own hospital for patient/encounter/admission/audit operations.
- `receptionist`:
  - Scoped to own hospital for patient and encounter-related visibility.
- `lab_technician`:
  - Lab order access constrained to own hospital and own lab unit.
  - Explicitly blocked from general patient record access by object-level helper.

---

## 6) Public + Authenticated Non-Role Endpoints

### Public endpoints
- `health` (GET)
- `auth/login` (POST)
- `auth/mfa-verify` (POST)
- `auth/activate` (POST)
- `auth/activate-setup` (GET, POST)
- `auth/forgot-password` (POST)
- `auth/reset-password` (POST)
- `auth/login-temp-password` (POST)

### Authenticated (any logged-in role)
- `auth/refresh` (POST)
- `auth/logout` (POST)
- `auth/me` (GET)
- `auth/change-password-on-login` (POST)

---

## 7) Single-Line Capability Snapshot

- `super_admin`: Full platform + cross-facility governance, system health, global audits, onboarding, advanced controls.
- `hospital_admin`: Facility operations/admin + user management + audits + clinical oversight in own facility.
- `doctor`: Clinical creation and management, AI clinical tools, referrals/consents, worklist.
- `nurse`: Ward operations, vitals/nursing workflows, shift/handover actions, limited clinical read + alert resolution.
- `receptionist`: Front-desk scheduling/appointments + patient search/read basics.
- `lab_technician`: Lab queue/results/attachments/analytics with lab-unit scoping.

