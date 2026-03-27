# MedSync RBAC by Module (Stakeholder-Friendly)

Last updated: 2026-03-27  
Companion file (full exhaustive endpoint list): `ROLE_BASED_USERS_PERMISSIONS_UI.md`

---

## Roles Covered

- `super_admin`
- `hospital_admin`
- `doctor`
- `nurse`
- `receptionist`
- `lab_technician`

---

## UI Access (Quick View)

| Role | Primary UI Modules |
|---|---|
| super_admin | Superadmin Dashboard, Hospitals, Cross-Facility Monitor, Global Audit, User Mgmt, Break-Glass Review, Facilities, System Health, AI Integration (+ clinical view-as) |
| hospital_admin | Dashboard, Patient Search, Appointments, Admissions, Alerts, Referrals, User Mgmt, Facility Config, RBAC Review, Audit Logs |
| doctor | Dashboard, Worklist, AI Insights, Patient Search, Appointments, Alerts, Referrals |
| nurse | Dashboard, Worklist, My Ward, Appointments, Alerts, Admissions |
| receptionist | Dashboard, Patient Search, Appointments |
| lab_technician | Dashboard, Lab Orders |

---

## Module-by-Module Permissions

## 1) Authentication & Session

### Public
- `GET /health`
- `POST /auth/login`
- `POST /auth/mfa-verify`
- `POST /auth/activate`
- `GET|POST /auth/activate-setup`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/login-temp-password`

### Any authenticated role
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/change-password-on-login`

---

## 2) Patient Registry & Chart

### Core
- Search patients: doctor, nurse, receptionist, lab_technician, hospital_admin, super_admin
- Create patient: doctor, hospital_admin
- Patient detail read:
  - doctor, nurse, receptionist, lab_technician, hospital_admin, super_admin
- Patient detail update:
  - hospital_admin, super_admin

### Clinical chart reads
- Diagnoses/Prescriptions/Records:
  - doctor, nurse (selected reads), hospital_admin, super_admin
- Labs:
  - doctor, lab_technician, hospital_admin, super_admin
- Vitals/Allergies:
  - doctor, nurse, hospital_admin, super_admin

### Encounters
- List: doctor, nurse, hospital_admin, super_admin
- Create: doctor, hospital_admin, super_admin
- Update/close: doctor, hospital_admin, super_admin

### Extra chart actions
- Export PDF: doctor, super_admin
- Duplicate-check: doctor, lab_technician, hospital_admin, super_admin

---

## 3) Clinical Records Creation

### Doctor-led creation
- Diagnosis, Prescription, Lab Order, Allergy, Radiology Order, Record Amend
- Roles: doctor, super_admin

### Nurse-led creation
- Vitals, Vitals Batch, Nursing Note, Dispense-by-nurse
- Roles: nurse, super_admin

### Shared/controlled actions
- Prescription dispense:
  - nurse (POST)
  - doctor/hospital_admin (PATCH)
  - super_admin (POST/PATCH)
- Drug/ICD autocomplete:
  - mostly doctor/hospital_admin/super_admin; nurses also for drug autocomplete

---

## 4) Appointments & Front Desk

### Scheduling lifecycle
- List/create/check-availability:
  - receptionist, doctor (selected), hospital_admin, super_admin
- Update:
  - receptionist, hospital_admin, super_admin
- Delete/check-in/reschedule/no-show:
  - receptionist, hospital_admin, super_admin

### Analytics
- No-show statistics:
  - receptionist, doctor, hospital_admin, super_admin

---

## 5) Admissions & Bed/Ward Flow

### Admissions
- List:
  - nurse, doctor, hospital_admin, super_admin
- Create:
  - doctor, hospital_admin, super_admin
- Discharge:
  - doctor, hospital_admin, super_admin

### Ward and bed admin
- Ward occupancy:
  - hospital_admin, super_admin, doctor, nurse
- Ward and bed management:
  - hospital_admin, super_admin

---

## 6) Alerts

### View alerts
- doctor, nurse, lab_technician, hospital_admin, super_admin

### Resolve alerts
- doctor, nurse only (`PATCH /alerts/<pk>/resolve`)

---

## 7) Lab Operations

### Lab worklist and execution
- Lab orders list/detail/result:
  - lab_technician, super_admin (doctor/hospital_admin read selected list routes)
- Bulk result submit:
  - lab_technician, super_admin
- Attachment upload:
  - lab_technician, super_admin
- Lab analytics trends:
  - lab_technician, super_admin

---

## 8) Admin, User Management & Governance

### User admin (facility/global)
- List/invite/bulk import/update role/status:
  - hospital_admin, super_admin
- Password reset/mfa reset/resend invite:
  - hospital_admin, super_admin
- RBAC review dashboard:
  - hospital_admin, super_admin
- Staff onboarding:
  - hospital_admin, super_admin

### Audit and export
- Admin audit logs:
  - hospital_admin, super_admin
- Audit export:
  - hospital_admin, super_admin

### Facility configuration
- Departments/lab units/lab test types/duplicates/wards/beds:
  - hospital_admin, super_admin (with route-specific GET/POST/PATCH)

---

## 9) Dashboard, Worklists, and Tasks

### Dashboard
- Basic dashboard metrics:
  - all six roles
- Analytics dashboard:
  - hospital_admin, super_admin

### Worklist
- Encounter/worklist:
  - doctor, nurse, hospital_admin, super_admin

### Async task status
- `tasks`, `tasks/<id>`, `tasks/<id>/result`:
  - all six roles (user-scoped by backend task ownership rules)

---

## 10) Interop, Referrals, Consents, Break-Glass

### Global patient interoperability
- Global patient search:
  - doctor, hospital_admin, super_admin
- Facility-patient link:
  - doctor, hospital_admin, super_admin
- Cross-facility records:
  - doctor, hospital_admin, super_admin

### Referrals
- Create/update/incoming:
  - doctor, hospital_admin, super_admin

### Consents
- Create/list/update:
  - doctor, hospital_admin, super_admin

### Break-glass (emergency access)
- Create/list:
  - doctor, hospital_admin, super_admin
- Global review/abuse workflows:
  - super_admin only

---

## 11) Super Admin Platform Controls

`super_admin` only:
- Global hospitals management
- System health
- Global audit logs and audit-chain validation
- Hospital onboarding workflows
- Cross-facility activity monitoring
- GMDC unverified doctor review
- Grant hospital access for other super admins
- Suspicious password reset monitoring
- Force password reset (Tier 3)

---

## 12) AI Intelligence Module

| Endpoint Group | doctor | nurse | hospital_admin | super_admin |
|---|---:|---:|---:|---:|
| Analyze patient | POST | POST | POST | POST |
| Risk prediction | POST | POST | - | POST |
| Clinical decision support | POST | - | - | POST |
| Triage | POST | POST | - | POST |
| Similar patients | POST | - | - | POST |
| Referral recommendation | POST | - | POST | POST |
| Analysis history | GET | GET | - | GET |
| AI status | - | - | - | GET |

---

## 13) Object-Level Restrictions (Critical)

RBAC route access is not the only check. The backend also enforces object scope:

- `doctor`: hospital-scoped; encounter access limited to assigned doctor or department.
- `nurse`: ward-scoped for active admissions/encounters; admission modification limited to own ward.
- `hospital_admin`: hospital-scoped data and governance.
- `receptionist`: hospital-scoped patient/appointment operations.
- `lab_technician`: hospital + lab-unit scoped lab operations; blocked from broad patient records.
- `super_admin`: global by default; may operate with selected view-as hospital context.

---

## 14) Role Capability Snapshot

- `super_admin`: full-system governance + global operational controls.
- `hospital_admin`: end-to-end facility administration + oversight.
- `doctor`: full clinical authoring + advanced AI decision support.
- `nurse`: ward workflows, vitals, handover, and alert response.
- `receptionist`: registration support and full appointment lifecycle.
- `lab_technician`: lab processing pipeline and lab analytics.

