# MedSync EMR: Architecture Documentation

**Status:** Production-Ready | **Version:** 1.0.0 | **Last Updated:** 2026-04-19

## Table of Contents

1. [System Overview](#system-overview)
2. [Authentication Flow](#authentication-flow)
3. [Multi-Tenancy Architecture](#multi-tenancy-architecture)
4. [Cross-Facility Access](#cross-facility-access)
5. [Database Schema](#database-schema)
6. [API Architecture](#api-architecture)
7. [Frontend Architecture](#frontend-architecture)
8. [Security Layers](#security-layers)
9. [Deployment Topology](#deployment-topology)
10. [Scalability Considerations](#scalability-considerations)

---

## System Overview

**MedSync** is a centralized, multi-hospital Electronic Medical Records (EMR) system designed for Ghana's inter-hospital network. It enables:

- **Multi-Hospital Management:** Centralized patient record management across independent hospital facilities
- **Role-Based Access Control (RBAC):** Fine-grained permissions for Doctors, Nurses, Lab Technicians, Receptionists, Hospital Admins, and Super Admins
- **Clinical Workflows:** Patient registration, appointment scheduling, encounter management, diagnosis, prescriptions, lab orders, and vital sign tracking
- **Health Information Exchange (HIE):** Cross-facility record sharing via consent, referrals, and emergency break-glass access
- **Audit & Compliance:** Comprehensive audit logging for HIPAA/GDPR compliance and regulatory reporting

### Core Principles

1. **Hospital-Scoped Access:** All data is owned and scoped by a hospital; users belong to one hospital
2. **Server-Side Authority:** The backend enforces all access control; frontend is a trusted UI client
3. **Consent-Based HIE:** Cross-facility access requires explicit consent or clinical justification
4. **Immutable Audit Trail:** All sensitive actions are logged with full context (user, timestamp, resource, action)

---

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│         MedSync Authentication (MFA MANDATORY)                   │
│                                                                   │
│  ⚠️  MFA is REQUIRED for all clinical roles with PHI access.    │
│  Exception: DEV_BYPASS_MFA=True in local development only.      │
└─────────────────────────────────────────────────────────────────┘

1. INITIAL LOGIN (Password + MANDATORY TOTP)
   ┌─────────────────────────────────────────┐
   │ User enters email + password on /login  │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ POST /auth/login                        │
   │ { email, password }                     │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ Backend validates credentials           │
   │ Check password against salted hash      │
   │ (bcrypt, no reuse of last 5 passwords)  │
   │ Check account lockout (5 attempts/15min)│
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ ✅ MANDATORY MFA CHECK                  │
   │ Verify user.is_mfa_enabled == True      │
   │ If not: Return 403 Forbidden            │
   │ (MFA is required, not optional)         │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ Generate MFA challenge                  │
   │ Channel: Email OTP OR TOTP Authenticator│
   │ Duration: 5 minutes (expires after)     │
   └──────────────┬──────────────────────────┘
                  ↓
   Return MFA token + channel info
   (TOTP authenticator required)
        ↓
   User enters TOTP code from authenticator
   ┌──────────────────────────┐
   │ POST /auth/verify-otp    │
   │ { mfa_token, code }      │
   └──────────┬───────────────┘
              ↓
        ┌──────────────────────────┐
        │ Validate TOTP code       │
        │ Check MFA session expiry  │
        │ Verify device/location    │
        └──────────┬───────────────┘
                  ↓
        ┌──────────────────────────┐
        │ Return JWT tokens:       │
        │ - access_token (15 min)  │
        │ - refresh_token (7 days) │
        │ (MFA verified flag set)  │
        └──────────────────────────┘

2. TOKEN USAGE (Access Protected Resources)
   ┌──────────────────────────────────────────┐
   │ GET /patients                            │
   │ Authorization: Bearer <access_token>     │
   │ X-View-As-Hospital: <hospital_id>       │
   │ (Super Admin only, optional)             │
   └──────────────┬───────────────────────────┘
                  ↓
   ┌──────────────────────────────────────────┐
   │ Backend verifies JWT signature           │
   │ Validates token expiration               │
   │ Checks user role + hospital scoping      │
   │ Returns 401 if invalid/expired           │
   └──────────────┬───────────────────────────┘
                  ↓
         ┌────────┴────────┐
         ↓                 ↓
    [Valid]           [Expired/Invalid]
         ↓                 ↓
    Return data       Return 401
                          ↓
                    Frontend retries with
                    refresh_token

3. TOKEN REFRESH (Keep Session Alive)
   ┌──────────────────────────────────────────┐
   │ POST /auth/refresh                       │
   │ { refresh_token }                        │
   └──────────────┬───────────────────────────┘
                  ↓
   ┌──────────────────────────────────────────┐
   │ Backend validates refresh token          │
   │ Checks blacklist (logout revocation)     │
   │ Rotates refresh token (new + invalidate) │
   │ Return new access_token + refresh_token  │
   └──────────────────────────────────────────┘

4. LOGOUT (Token Blacklist)
   ┌──────────────────────────────────────────┐
   │ POST /auth/logout                        │
   │ { refresh_token }                        │
   └──────────────┬───────────────────────────┘
                  ↓
   ┌──────────────────────────────────────────┐
   │ Backend adds tokens to blacklist         │
   │ (Redis cache + DB for audit)             │
   │ Frontend clears local tokens             │
   └──────────────────────────────────────────┘

5. PASSKEY/WebAuthn (Optional Passwordless)
   ┌──────────────────────────────────────────┐
   │ POST /auth/register-passkey              │
   │ User enrolls biometric/security key      │
   │ WebAuthn credential stored in DB         │
   └──────────────┬───────────────────────────┘
                  ↓
   ┌──────────────────────────────────────────┐
   │ POST /auth/login-passkey                 │
   │ Browser prompts for biometric/key        │
   │ Backend verifies signature               │
   │ Return JWT tokens (same as password)     │
   └──────────────────────────────────────────┘
```

**Token Lifecycle:**

| Token | TTL | Usage | Refresh | Blacklist |
|-------|-----|-------|---------|-----------|
| `access_token` | 15 min | API requests | AUTO on 401 | Manual on logout |
| `refresh_token` | 7 days | Get new access_token | Rotated per refresh | Manual on logout |

**Security Details:**

- **JWT Library:** `djangorestframework-simplejwt` with explicit HS256 signing
- **Password Storage:** bcrypt (cost factor 12), no plaintext ever
- **MFA:** TOTP (Time-Based OTP) via `pyotp` — **MANDATORY for all clinical roles with PHI access**
  - All doctors, nurses, lab technicians, hospital admins: MFA REQUIRED
  - Super admins: MFA REQUIRED
  - Exception: Local development only with `DEV_BYPASS_MFA=True` environment variable
  - Implementation enforces: `if not user.is_mfa_enabled: return 403 Forbidden`
- **Token Blacklist:** Redis for fast revocation checks; DB for audit trail
- **WebAuthn/Passkey:** Optional passwordless authentication (replaces password, but MFA still required)

---

## Multi-Tenancy Architecture

MedSync enforces **hospital-scoped access** at every layer.

### Data Model

```
┌─────────────────────────────────────────┐
│          Hospital (Facility)            │
│  ┌────────────────────────────────────┐ │
│  │ id, name, code, region, active     │ │
│  │ contact_email, phone, address      │ │
│  └────────────────────────────────────┘ │
└─────────────────┬───────────────────────┘
                  │
                  ├──← Owns ──→ User (Staff)
                  │           ├─ role (doctor, nurse, admin, ...)
                  │           ├─ hospital_id (FK)
                  │           ├─ ward_id (optional, nurse only)
                  │           └─ active, mfa_enabled
                  │
                  ├──← Owns ──→ Patient (Demographics)
                  │           ├─ ghana_health_id (unique PER HOSPITAL)
                  │           ├─ registered_at (hospital FK)
                  │           ├─ name, dob, gender
                  │           └─ contact info
                  │
                  └──← Owns ──→ PatientAdmission (Ward Stay)
                              ├─ patient_id (FK)
                              ├─ ward_id (FK)
                              ├─ admitted_at, discharged_at
                              └─ admission_reason, bed_number
```

### Access Control Rules

**Non-Super Admin Users (Doctor, Nurse, Lab Tech, etc.):**

```python
# Query scoping: users see only their hospital's data
queryset = queryset.filter(hospital=user.hospital)

# Nurse: restricted to ward
if user.role == 'nurse':
    queryset = queryset.filter(admission__ward__nurse=user)

# Lab Tech: sees only labs for their hospital
if user.role == 'lab_technician':
    queryset = queryset.filter(order__hospital=user.hospital)
```

**Super Admin:**

```python
# Can see ALL hospitals' data
# No hospital_id filter applied
# But can use X-View-As-Hospital header for per-hospital audit context
# Backend logs which hospital was viewed for compliance
```

### Hospital Context Enforcement

Every API request that modifies/creates data validates:

```python
def create_encounter(request, patient_id):
    patient = Patient.objects.get(id=patient_id)
    user_hospital = get_effective_hospital(request)
    
    # Verify patient belongs to user's hospital
    if patient.registered_at != user_hospital:
        return 403 Forbidden  # Cross-facility without consent
    
    # Only then proceed with create
    encounter = Encounter.objects.create(
        patient=patient,
        hospital=user_hospital,
        provider=request.user
    )
```

---

## Cross-Facility Access

### Three Mechanisms for Multi-Hospital Records

#### 1. Consent Model

```
Hospital A Doctor creates CONSENT for a patient, granting Hospital B access.

┌──────────────────────────────────────────────────┐
│ Consent                                          │
│ ┌──────────────────────────────────────────────┐ │
│ │ id, patient_id                               │ │
│ │ granted_by (Hospital A user)                 │ │
│ │ granted_to (Hospital B, or user)             │ │
│ │ scope: "SUMMARY" | "FULL_RECORD"             │ │
│ │ valid_from, valid_until (expiry)             │ │
│ │ revoked_at (null = active)                   │ │
│ └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘

Hospital B user GET /patients/<patient_id>/records
  ↓
Backend checks:
  1. Does patient exist? (from Hospital A)
  2. Is there an active CONSENT from Hospital A to this user's hospital?
  3. If FULL_RECORD: return all data
     If SUMMARY: return only demographics (HIPAA safe harbor)
  4. Log action: "VIEW_CROSS_FACILITY" with scope + reason
```

**Audit Trail:**

```
AuditLog {
  user: doctor@hospitalB.gh,
  action: "VIEW_CROSS_FACILITY",
  resource_id: "<patient_id>",  # sanitized (no PHI)
  hospital: HospitalB,
  details: {
    cross_facility_hospital: HospitalA,
    consent_scope: "FULL_RECORD",
    consent_expires: "2026-06-30",
    timestamp: "2026-04-19T10:30:00Z"
  }
}
```

#### 2. Referral Model

```
Hospital A Doctor creates REFERRAL to Hospital B for a patient.

┌──────────────────────────────────────────────────┐
│ Referral                                         │
│ ┌──────────────────────────────────────────────┐ │
│ │ id, patient_id, from_hospital, to_hospital   │ │
│ │ referred_by (Hospital A doctor)              │ │
│ │ reason, clinical_summary                     │ │
│ │ status: "pending" | "accepted" | "rejected"  │ │
│ │ accepted_by (Hospital B doctor)              │ │
│ │ created_at, updated_at                       │ │
│ └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘

Acceptance Flow:
  1. Hospital A doctor creates referral + grants temporary CONSENT
  2. Hospital B doctor sees referral in inbox
  3. Doctor can ACCEPT (creates ongoing consent for specialists)
     or REJECT (consent expires)
  4. Once accepted, Hospital B can treat patient and access full records
```

#### 3. Break-Glass (Emergency Override)

```
LAST RESORT: Any authorized clinical staff can access ANY patient record
for 15 minutes if in critical medical emergency.

┌──────────────────────────────────────────────────┐
│ BreakGlassLog                                    │
│ ┌──────────────────────────────────────────────┐ │
│ │ id, patient_id, accessed_by (user)           │ │
│ │ hospital (accessing hospital)                │ │
│ │ reason (required, free text)                 │ │
│ │ medical_justification (required)             │ │
│ │ initiated_at, expires_at (15 min)            │ │
│ │ reviewed_by (compliance officer)             │ │
│ │ reviewed_at, review_notes                    │ │
│ └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘

Access Attempt:
  User GET /patients/<patient_id>/records
  If permission denied (different hospital, no consent):
    → Prompt: "BREAK-GLASS: Justify emergency access"
    → User enters: reason + medical justification
    → System creates BreakGlassLog(expires_at = now + 15min)
    → User can access for 15 min
    → After expiry: access denied again
    → Hospital compliance team reviews logs daily
    → Super admin notified of suspicious patterns
```

**Audit Trail (Full):**

```
Multiple AuditLog entries:
1. {action: "BREAK_GLASS_INITIATED", reason: "...", timestamp: ...}
2. {action: "VIEW_CROSS_FACILITY", scope: "EMERGENCY", timestamp: ...}
3. (Any modifications, DELETE, etc.)
4. {action: "BREAK_GLASS_EXPIRED", timestamp: ...}
```

---

## Database Schema

### 20+ Core Models

```
HOSPITAL GOVERNANCE
├─ Hospital (Facility registration)
│  ├─ id (UUID)
│  ├─ name, code, region
│  ├─ contact_email, phone, address
│  ├─ active (bool)
│  └─ metadata (JSON: accreditation, capacity, etc.)
│
├─ Ward (Hospital division)
│  ├─ id, hospital_id (FK)
│  ├─ name (e.g. "Cardiology", "ICU")
│  ├─ capacity (beds)
│  └─ chief_nurse (User FK, optional)
│
└─ User (Staff account)
   ├─ id, email (unique), password (bcrypt)
   ├─ first_name, last_name, phone
   ├─ hospital_id (FK) — which hospital this user works for
   ├─ ward_id (FK, nullable) — nurse assignment
   ├─ role (enum: super_admin, hospital_admin, doctor, nurse, lab_technician, receptionist)
   ├─ active, mfa_enabled, last_login
   └─ metadata (JSON: license, specialties, etc.)

PATIENT DATA (Per Hospital)
├─ Patient (Demographics, hospital-scoped)
│  ├─ id (UUID)
│  ├─ ghana_health_id (str, unique PER hospital)
│  ├─ first_name, last_name, dob, gender
│  ├─ registered_at (Hospital FK)
│  ├─ contact_phone, address, emergency_contact
│  ├─ blood_type, allergies (JSON)
│  ├─ active_admission (PatientAdmission FK, nullable)
│  └─ created_at, updated_at
│
├─ PatientAdmission (Ward stay)
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ hospital_id (FK)
│  ├─ ward_id (FK)
│  ├─ bed_number (str, optional)
│  ├─ admitted_at, discharged_at (nullable)
│  ├─ admission_reason, discharge_summary
│  ├─ admitted_by (User FK)
│  └─ updated_at
│
├─ Appointment (Scheduling)
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ hospital_id (FK)
│  ├─ scheduled_by (Receptionist FK)
│  ├─ provider_id (Doctor FK, nullable — can be set later)
│  ├─ department (str)
│  ├─ scheduled_at (datetime)
│  ├─ status (enum: pending, checked_in, completed, no_show, cancelled)
│  ├─ checked_in_at (nullable)
│  └─ completed_at (nullable)
│
└─ Encounter (Clinical visit)
   ├─ id (UUID)
   ├─ patient_id (FK)
   ├─ hospital_id (FK)
   ├─ provider_id (Doctor/Nurse FK)
   ├─ appointment_id (FK, nullable)
   ├─ encounter_type (enum: inpatient, outpatient, emergency)
   ├─ chief_complaint (text)
   ├─ status (enum: draft, active, completed, closed)
   ├─ started_at, ended_at
   ├─ clinical_notes (text, nullable)
   └─ created_at, updated_at

CLINICAL RECORDS (Per Encounter)
├─ Diagnosis
│  ├─ id, encounter_id (FK)
│  ├─ icd10_code (str, e.g. "J18.9")
│  ├─ description, confidence_score
│  └─ primary (bool) — main diagnosis for billing
│
├─ Prescription
│  ├─ id, encounter_id (FK)
│  ├─ medication_name (str)
│  ├─ dosage, unit, frequency
│  ├─ duration_days
│  ├─ prescribed_by (User FK)
│  ├─ prescribed_at, dispensed_at (nullable)
│  └─ status (enum: pending, dispensed, cancelled)
│
├─ Vital (Vital signs)
│  ├─ id, encounter_id (FK) or patient_id (FK)
│  ├─ temperature_celsius (float)
│  ├─ systolic_bp, diastolic_bp
│  ├─ heart_rate_bpm
│  ├─ respiratory_rate_bpm
│  ├─ oxygen_saturation_percent
│  ├─ recorded_by (User FK)
│  ├─ recorded_at
│  └─ flags (JSON: abnormal values, alerts)
│
├─ LabOrder
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ hospital_id (FK)
│  ├─ encounter_id (FK, nullable)
│  ├─ ordered_by (Doctor FK)
│  ├─ test_name (e.g. "Full Blood Count")
│  ├─ loinc_code (standardized code)
│  ├─ ordered_at, collected_at (nullable)
│  ├─ status (enum: pending, collected, in_progress, completed, cancelled)
│  └─ notes
│
├─ LabResult
│  ├─ id (UUID)
│  ├─ lab_order_id (FK)
│  ├─ result_value (str/float)
│  ├─ unit (str, e.g. "g/dL")
│  ├─ normal_range_min, normal_range_max
│  ├─ flag (enum: normal, abnormal, critical)
│  ├─ interpretation (text)
│  ├─ verified_by (Lab Tech FK)
│  ├─ verified_at
│  └─ report_sent_at (nullable)
│
├─ NursingNote
│  ├─ id (UUID)
│  ├─ encounter_id (FK)
│  ├─ recorded_by (Nurse FK)
│  ├─ note_text (text)
│  ├─ care_provided (JSON: interventions, observations)
│  ├─ recorded_at
│  └─ shift_handover (bool) — used during shift end
│
└─ MedicalRecord (Generic container for other docs)
   ├─ id (UUID)
   ├─ encounter_id (FK)
   ├─ record_type (enum: imaging, pathology, procedure_note, discharge_summary)
   ├─ document_url (S3 path, if applicable)
   ├─ text_content (if stored inline)
   └─ created_by, created_at

HEALTH INFORMATION EXCHANGE (HIE)
├─ GlobalPatient (Master record across hospitals)
│  ├─ id (UUID)
│  ├─ external_id (str, optional — links to external registry)
│  └─ created_at (timestamp when first registered)
│
├─ FacilityPatient (Link from Hospital → GlobalPatient)
│  ├─ id
│  ├─ global_patient_id (FK)
│  ├─ facility_patient_id (FK — local Patient)
│  ├─ hospital_id (FK)
│  └─ confirmed_match (bool) — manual review required
│
├─ Consent (Data sharing permission)
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ from_hospital (FK) — who grants
│  ├─ to_hospital (FK) — who receives
│  ├─ granted_by (User FK)
│  ├─ scope (enum: SUMMARY, FULL_RECORD)
│  ├─ valid_from, valid_until (dates)
│  ├─ revoked_at (nullable)
│  └─ created_at, updated_at
│
├─ Referral (Inter-hospital referral)
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ from_hospital (FK)
│  ├─ to_hospital (FK)
│  ├─ referred_by (User FK — Doctor at from_hospital)
│  ├─ reason (text, clinical summary)
│  ├─ status (enum: pending, accepted, rejected, completed)
│  ├─ accepted_by (User FK, nullable — Doctor at to_hospital)
│  ├─ created_at, updated_at
│  └─ metadata (JSON: specialty needed, urgency, etc.)
│
└─ BreakGlassLog (Emergency access override)
   ├─ id (UUID)
   ├─ patient_id (FK)
   ├─ accessed_by (User FK)
   ├─ hospital (FK) — which hospital initiated override
   ├─ reason (text, required)
   ├─ medical_justification (text, required)
   ├─ initiated_at, expires_at (15 min window)
   ├─ reviewed_by (User FK, compliance officer)
   ├─ review_notes (text)
   └─ status (enum: active, expired, revoked, approved)

GOVERNANCE & COMPLIANCE
├─ AuditLog (Complete activity log)
│  ├─ id (UUID)
│  ├─ user_id (FK)
│  ├─ action (enum: CREATE, UPDATE, DELETE, VIEW, VIEW_CROSS_FACILITY, BREAK_GLASS, LOGIN, etc.)
│  ├─ resource_type (str, e.g. "Encounter", "Patient")
│  ├─ resource_id (str, sanitized to avoid logging PHI)
│  ├─ hospital_id (FK) — which hospital's context
│  ├─ timestamp (auto_now_add)
│  ├─ ip_address (str)
│  ├─ user_agent (str, optional)
│  ├─ details (JSON: before/after values, cross_facility_scope, etc.)
│  ├─ status (enum: success, error)
│  └─ error_message (nullable)
│
├─ UserPasswordHistory (Enforce no-reuse)
│  ├─ id, user_id (FK)
│  ├─ password_hash (bcrypt)
│  └─ created_at
│
├─ UserSession (Track active logins)
│  ├─ id (UUID)
│  ├─ user_id (FK)
│  ├─ token_jti (str, unique identifier from JWT)
│  ├─ created_at, expires_at
│  ├─ ip_address, user_agent
│  └─ revoked (bool) — logout or token blacklist
│
└─ SystemAlert (Clinical and operational alerts)
   ├─ id (UUID)
   ├─ alert_type (enum: clinical_risk, overdue_order, bed_alert, supply_low, system_error)
   ├─ patient_id (FK, optional)
   ├─ hospital_id (FK)
   ├─ message (str)
   ├─ severity (enum: info, warning, critical)
   ├─ created_at, acknowledged_at (nullable)
   ├─ acknowledged_by (User FK, nullable)
   └─ auto_resolved_at (nullable)

AI/ML ANALYSIS (Optional)
├─ AIAnalysis (Top-level analysis)
│  ├─ id (UUID)
│  ├─ patient_id (FK)
│  ├─ hospital_id (FK)
│  ├─ analysis_type (enum: risk_prediction, differential_diagnosis, readmission_risk, etc.)
│  ├─ overall_confidence (float 0-1)
│  ├─ clinical_summary (text)
│  ├─ recommended_actions (JSON list)
│  ├─ alerts (JSON)
│  ├─ created_at
│  └─ metadata (JSON)
│
├─ DiseaseRiskPrediction (Disease scores)
│  ├─ id, analysis_id (FK)
│  ├─ disease_name, icd10_code
│  ├─ risk_score (float 0-1)
│  └─ confidence
│
└─ TriageAssessment (Emergency severity)
   ├─ id, analysis_id (FK)
   ├─ severity (enum: green, yellow, orange, red)
   ├─ recommendation (text)
   └─ confidence
```

### ER Diagram (Simplified)

```
Hospital ──┬─→ Ward ──→ PatientAdmission
           ├─→ User
           ├─→ Patient ──→ Appointment
           │           ├─→ Encounter ──┬─→ Diagnosis
           │           │               ├─→ Prescription
           │           │               ├─→ Vital
           │           │               └─→ NursingNote
           │           ├─→ LabOrder ──→ LabResult
           │           └─→ GlobalPatient
           │
           └─→ Consent ←─┤ (Referral)
               BreakGlassLog
               AuditLog
               SystemAlert
```

---

## API Architecture

### REST Framework: Django REST Framework (DRF)

**Technology Stack:**

- **Framework:** Django 4.2+, DRF 3.14+
- **Authentication:** `djangorestframework-simplejwt` with explicit **HS256** (HMAC-SHA256) signing
- **Permissions:** Custom RBAC middleware + DRF permissions
- **Serializers:** Nested serializers for complex resources
- **Pagination:** Cursor-based (for large datasets)
- **Throttling:** Token-bucket rate limiting (per user, per endpoint)

**JWT Algorithm Details:**

| Token Type | Algorithm | Usage | Why |
|-----------|-----------|-------|-----|
| `access_token` (15 min) | HS256 (Symmetric) | API authentication | Backend only has secret; safely signs & verifies |
| `refresh_token` (7 days) | HS256 (Symmetric) | Token renewal | Backend only has secret; safely signs & verifies |
| Cross-facility X-Consent-Token | RS256 (Asymmetric, Future) | Inter-hospital token verification | ⚠️ IF IMPLEMENTED: Private key (signer) kept by central platform; public keys (verifier) distributed to hospitals. Using HS256 for multi-party would allow forging. |

**Algorithm Security Model:**

- **HS256 (Current):** Safe because only the backend has the shared secret. Backend both signs tokens and verifies them. No external parties have the secret.
- **RS256 (If X-Consent-Token Added):** Required for cross-hospital scenarios where a receiving hospital must verify authenticity without being able to forge tokens. Private key stays with the central platform; hospitals receive public key for verification only.
- **Current Cross-Facility Access:** Uses **database queries** (Consent, Referral, BreakGlassLog models), not JWT tokens. This is actually safer than JWT tokens would be because tokens cannot be replayed and are immediately revocable.

**See Also:** `api/tests/test_jwt_algorithm.py` for algorithm verification tests and security requirements.

### View Organization

```
api/views/
├─ patient_views.py         # Patient CRUD, search, registration
├─ encounter_views.py       # Encounter lifecycle
├─ record_views.py          # Diagnoses, prescriptions, vitals
├─ appointment_views.py     # Appointment scheduling
├─ lab_views.py             # Lab orders and results
├─ admin_views.py           # Hospital admin operations (staff, wards)
├─ auth_views.py            # Login, refresh, logout, MFA
├─ hie_views.py             # Consent, referrals, break-glass
├─ audit_views.py           # Audit log queries
├─ fhir_views.py            # FHIR-compliant read-only endpoints
├─ hl7_views.py             # HL7 export
└─ dashboard_views.py       # Role-specific dashboards
```

### Serializer Hierarchy

```python
# Base serializer with hospital scoping
class HospitalScopedSerializer(serializers.ModelSerializer):
    def validate(self, data):
        # Enforce hospital_id matches user.hospital
        user_hospital = get_effective_hospital(self.context['request'])
        if data.get('hospital') and data['hospital'] != user_hospital:
            raise PermissionDenied("Cannot create resource in another hospital")
        return data

# Nested resources
class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = ['id', 'icd10_code', 'description', 'primary']

class EncounterDetailSerializer(HospitalScopedSerializer):
    diagnoses = DiagnosisSerializer(many=True, read_only=True)
    vitals = VitalSerializer(many=True, read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Encounter
        fields = [...]
```

### Endpoint Patterns

```
# Authentication
POST   /auth/login              # {email, password} → {access_token, refresh_token}
POST   /auth/verify-otp         # {code} → {access_token}
POST   /auth/refresh            # {refresh_token} → {new_access_token}
POST   /auth/logout             # {refresh_token} → 200 OK
POST   /auth/register-passkey   # WebAuthn enrollment
POST   /auth/login-passkey      # WebAuthn login

# Patient Management (Hospital-Scoped)
GET    /patients/               # List patients in user's hospital
POST   /patients/register       # Register new patient
GET    /patients/<id>/          # Get patient details
GET    /patients/search         # Full-text search (hospital-scoped)
GET    /patients/<id>/records   # All clinical records (with consent check)
GET    /patients/<id>/export/pdf # PDF export
DELETE /patients/<id>/          # Soft delete (compliance)

# Appointment (Receptionist)
GET    /appointments/           # List appointments
POST   /appointments/           # Schedule appointment
PATCH  /appointments/<id>/      # Check-in, reschedule
POST   /appointments/<id>/check-in
PATCH  /appointments/<id>/check-out

# Encounter (Doctor/Nurse)
POST   /encounters/             # Create encounter (draft)
GET    /encounters/<id>/        # Get encounter
PATCH  /encounters/<id>/        # Update encounter
POST   /encounters/<id>/close   # Close encounter (final)
POST   /encounters/<id>/add-diagnosis    # Add diagnosis
POST   /encounters/<id>/add-prescription # Add prescription
POST   /encounters/<id>/add-vital        # Record vitals
POST   /encounters/<id>/add-note         # Add nursing note

# Lab Orders (Doctor/Lab Tech)
GET    /lab-orders/             # List pending orders
POST   /lab-orders/             # Create order
GET    /lab-orders/<id>/        # Order details
POST   /lab-orders/<id>/collect # Mark collected
POST   /lab-orders/<id>/enter-results  # Lab tech enters results
PATCH  /lab-orders/<id>/verify  # Verify results
POST   /lab-orders/<id>/complete# Complete order

# HIE: Consent & Referral
GET    /hie/consents/           # List consents granted by user's hospital
POST   /hie/consents/           # Grant consent to another hospital
PATCH  /hie/consents/<id>/revoke # Revoke consent

GET    /hie/referrals/          # List referrals (sent and received)
POST   /hie/referrals/          # Create referral to another hospital
POST   /hie/referrals/<id>/accept # Accept referral (Hospital B)
POST   /hie/referrals/<id>/reject
GET    /hie/referrals/<id>/      # Referral details

# Break-Glass (Emergency Override)
POST   /hie/break-glass/        # Initiate emergency access
GET    /hie/break-glass/logs    # View break-glass history (super admin/compliance)
PATCH  /hie/break-glass/<id>/   # Compliance review

# Audit & Compliance
GET    /audit/logs/             # Search audit logs (admin/super admin)
GET    /audit/logs/<id>/        # Audit entry details

# Admin: Staff Management
GET    /admin/staff/            # List hospital staff
POST   /admin/staff/invite      # Invite staff (send email)
PATCH  /admin/staff/<id>/       # Update role, ward assignment
DELETE /admin/staff/<id>/       # Deactivate staff
POST   /admin/staff/<id>/reset-mfa # Reset MFA

# Admin: Wards
GET    /admin/wards/            # List wards
POST   /admin/wards/            # Create ward
PATCH  /admin/wards/<id>/       # Update ward (capacity, chief)

# Health & System
GET    /health                  # System health (no auth required)
GET    /health/db               # Database connectivity
GET    /health/cache            # Redis connectivity

# FHIR (Read-Only, Cross-Hospital)
GET    /fhir/Patient/<id>       # FHIR Patient resource
GET    /fhir/Encounter/<id>     # FHIR Encounter resource
GET    /fhir/Condition/<id>     # FHIR Condition (Diagnosis)
GET    /fhir/Medication/<id>    # FHIR Medication
```

### Permission Classes

```python
class IsAuthenticated(permissions.BasePermission):
    """User must be logged in and have valid hospital assignment."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

class IsDoctorOrNurse(permissions.BasePermission):
    """Clinical staff only."""
    def has_permission(self, request, view):
        return request.user.role in ['doctor', 'nurse']

class IsHospitalAdmin(permissions.BasePermission):
    """Hospital admin or super admin."""
    def has_permission(self, request, view):
        return request.user.role in ['hospital_admin', 'super_admin']

class IsHospitalScoped(permissions.BasePermission):
    """Resource must belong to user's hospital (enforced in view)."""
    def has_object_permission(self, request, view, obj):
        user_hospital = get_effective_hospital(request)
        return obj.hospital == user_hospital
```

### Rate Limiting

```
# Per user, per endpoint
200 requests / hour for doctor (GET/POST)
50 requests / hour for patient registration
10 requests / hour for login attempts (brute-force protection)

# Per IP (API clients)
1000 requests / hour per IP

# Enforcement: DRF throttling + Redis backend
# On limit exceeded: 429 Too Many Requests
```

---

## Frontend Architecture

### Tech Stack

- **Framework:** Next.js 16 with App Router
- **UI Library:** React 19 (Hooks, Context API)
- **Language:** TypeScript 5 (strict mode)
- **Styling:** Tailwind CSS 4 + PostCSS
- **State Management:** React Context (auth, hospital), zustand (optional)
- **HTTP Client:** Fetch + custom retry logic
- **Testing:** Vitest + Playwright (E2E)
- **Build:** Next.js built-in (Webpack 5+)

### Directory Structure

```
medsync-frontend/src/
├─ app/                        # Next.js App Router
│  ├─ (auth)/                  # Public auth routes (no layout)
│  │  ├─ login/page.tsx        # /login
│  │  ├─ register/page.tsx     # /register
│  │  └─ layout.tsx            # Auth layout (minimal)
│  │
│  ├─ (dashboard)/             # Protected dashboard routes
│  │  ├─ dashboard/page.tsx    # /dashboard (role-based landing)
│  │  ├─ layout.tsx            # Dashboard layout (sidebar, topbar)
│  │  ├─ patients/
│  │  │  ├─ page.tsx           # /patients (list/search)
│  │  │  ├─ [id]/page.tsx      # /patients/<id> (detail)
│  │  │  ├─ [id]/encounters/page.tsx # /patients/<id>/encounters
│  │  │  └─ register/page.tsx  # /patients/register (receptionist)
│  │  ├─ encounters/
│  │  │  ├─ [id]/page.tsx      # /encounters/<id> (detail + edit)
│  │  │  └─ create/page.tsx    # /encounters/create
│  │  ├─ appointments/page.tsx # /appointments (scheduling)
│  │  ├─ lab/
│  │  │  ├─ orders/page.tsx    # /lab/orders
│  │  │  └─ [id]/page.tsx      # /lab/<id> (order detail)
│  │  ├─ admin/
│  │  │  ├─ staff/page.tsx     # /admin/staff
│  │  │  ├─ wards/page.tsx     # /admin/wards
│  │  │  └─ audit/page.tsx     # /admin/audit
│  │  ├─ hie/
│  │  │  ├─ consents/page.tsx  # /hie/consents
│  │  │  ├─ referrals/page.tsx # /hie/referrals
│  │  │  └─ break-glass/page.tsx
│  │  └─ settings/page.tsx     # /settings (user profile, MFA, passkeys)
│  │
│  ├─ error.tsx                # Error boundary
│  ├─ not-found.tsx            # 404 page
│  └─ layout.tsx               # Root layout
│
├─ components/                 # React components
│  ├─ layout/
│  │  ├─ Sidebar.tsx           # Navigation sidebar
│  │  ├─ TopBar.tsx            # Header with user menu
│  │  └─ RoleBasedNav.tsx       # Nav items by role
│  │
│  ├─ features/
│  │  ├─ patients/
│  │  │  ├─ PatientSearch.tsx
│  │  │  ├─ PatientForm.tsx    # Registration/edit
│  │  │  ├─ PatientDetail.tsx
│  │  │  └─ VitalCard.tsx
│  │  ├─ encounters/
│  │  │  ├─ EncounterForm.tsx
│  │  │  ├─ DiagnosisForm.tsx
│  │  │  ├─ PrescriptionForm.tsx
│  │  │  └─ EncounterDetail.tsx
│  │  ├─ appointments/
│  │  │  └─ AppointmentScheduler.tsx
│  │  ├─ lab/
│  │  │  ├─ LabOrderForm.tsx
│  │  │  └─ LabResultForm.tsx
│  │  └─ admin/
│  │     ├─ StaffInvite.tsx
│  │     └─ AuditLogViewer.tsx
│  │
│  ├─ ui/                      # Reusable UI components (headless)
│  │  ├─ Button.tsx
│  │  ├─ Input.tsx
│  │  ├─ Select.tsx
│  │  ├─ Dialog.tsx
│  │  ├─ Card.tsx
│  │  ├─ Alert.tsx
│  │  ├─ Badge.tsx
│  │  └─ Spinner.tsx
│  │
│  └─ common/
│     ├─ Loading.tsx
│     ├─ ErrorBoundary.tsx
│     └─ ProtectedRoute.tsx
│
├─ hooks/                      # Custom React hooks
│  ├─ use-auth.ts              # Auth context + token management
│  ├─ use-patients.ts          # Patient API calls
│  ├─ use-encounters.ts        # Encounter CRUD
│  ├─ use-appointments.ts      # Appointment scheduling
│  ├─ use-lab.ts               # Lab orders/results
│  ├─ use-hie.ts               # Consent/referral/break-glass
│  ├─ use-admin.ts             # Staff management, audit logs
│  └─ use-api.ts               # Generic API hook (token retry logic)
│
├─ lib/                        # Utilities
│  ├─ api-client.ts            # Fetch wrapper + error handling
│  ├─ api-base.ts              # API_BASE URL config
│  ├─ auth-context.tsx         # React Context for auth state
│  ├─ types.ts                 # TypeScript interfaces (API responses)
│  ├─ password-policy.ts       # Client-side password validation (mirrors backend)
│  ├─ constants.ts             # Enums, role colors, etc.
│  ├─ utils.ts                 # Helper functions
│  ├─ i18n/                    # Internationalization
│  │  ├─ en.json               # English strings
│  │  ├─ fr.json               # French
│  │  ├─ ak.json               # Akan
│  │  └─ es.json               # Spanish
│  └─ storage.ts               # LocalStorage/SessionStorage wrappers
│
├─ styles/                     # Global CSS
│  ├─ globals.css              # Tailwind + custom CSS
│  └─ variables.css            # CSS custom properties
│
└─ public/                     # Static assets
   └─ logos, icons, etc.
```

### Authentication Flow (Frontend)

```typescript
// app/(auth)/login/page.tsx
export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const router = useRouter();

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json();
        // If MFA required, show MFA form; else store tokens
        if (data.mfa_required) {
          setMfaRequired(true);
        } else {
          localStorage.setItem("access_token", data.access_token);
          sessionStorage.setItem("refresh_token", data.refresh_token);
          router.push("/dashboard");
        }
      }
    } catch (err) {
      // Error handling
    }
  };
}

// lib/auth-context.tsx
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);

  useEffect(() => {
    // Hydrate from localStorage on mount
    const stored = localStorage.getItem("access_token");
    if (stored) {
      setToken(stored);
      fetchUser(stored);
    }
  }, []);

  const fetchUser = async (token) => {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      setUser(await res.json());
    } else if (res.status === 401) {
      // Try refresh
      const newToken = await refreshToken();
      if (newToken) {
        fetchUser(newToken);
      }
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, setToken }}>
      {children}
    </AuthContext.Provider>
  );
}

// hooks/use-api.ts
export function useApi() {
  const { token, setToken } = useAuth();

  const request = async (path, options = {}) => {
    let res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Authorization": `Bearer ${token}`,
        ...options.headers,
      },
    });

    if (res.status === 401) {
      // Token expired, try refresh
      const newToken = await refreshToken();
      if (newToken) {
        setToken(newToken);
        res = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers: {
            "Authorization": `Bearer ${newToken}`,
            ...options.headers,
          },
        });
      } else {
        // Redirect to login
        router.push("/login");
      }
    }

    return res.json();
  };

  return { request };
}
```

### Role-Based UI

```typescript
// lib/constants.ts
export const ROLES = {
  SUPER_ADMIN: "super_admin",
  HOSPITAL_ADMIN: "hospital_admin",
  DOCTOR: "doctor",
  NURSE: "nurse",
  LAB_TECH: "lab_technician",
  RECEPTIONIST: "receptionist",
};

export const roleAccentColours = {
  super_admin: "bg-red-100 text-red-800 border-red-300",
  hospital_admin: "bg-purple-100 text-purple-800 border-purple-300",
  doctor: "bg-blue-100 text-blue-800 border-blue-300",
  nurse: "bg-green-100 text-green-800 border-green-300",
  lab_technician: "bg-amber-100 text-amber-800 border-amber-300",
  receptionist: "bg-gray-100 text-gray-800 border-gray-300",
};

// components/layout/RoleBasedNav.tsx
export function RoleBasedNav() {
  const { user } = useAuth();

  const navByRole = {
    [ROLES.DOCTOR]: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Patients", href: "/patients" },
      { label: "Appointments", href: "/appointments" },
      { label: "Lab Orders", href: "/lab/orders" },
      { label: "Cross-Facility", href: "/hie/referrals" },
    ],
    [ROLES.NURSE]: [
      { label: "Ward", href: "/dashboard" },
      { label: "Patients", href: "/patients" },
      { label: "Vitals", href: "/vitals" },
    ],
    // ... etc
  };

  const items = navByRole[user.role] || [];

  return (
    <nav>
      {items.map((item) => (
        <Link key={item.href} href={item.href}>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
```

---

## Security Layers

### 1. Authentication Layer

```
┌──────────────────────────────────────────────────────────────┐
│ Authentication (MFA MANDATORY for Clinical Roles)            │
├──────────────────────────────────────────────────────────────┤
│ ✓ Password: 12+ chars, complexity rules                      │
│ ✓ Bcrypt hashing (cost 12)                                   │
│ ✓ No plaintext storage                                       │
│ ✓ TOTP MFA: MANDATORY for all clinical roles (doctors,       │
│   nurses, lab techs, hospital admins, super admins)          │
│   Exception: DEV_BYPASS_MFA=True in local dev only          │
│ ✓ WebAuthn/Passkey support (replaces password, MFA still req)│
│ ✓ Session management (JWT + blacklist)                       │
│ ✓ Token rotation on refresh│
│ ✓ Rate limiting (10 login attempts/hr)  │
└──────────────────────────────────────────┘
```

### 2. Authorization Layer (RBAC + Hospital Scoping)

```
┌──────────────────────────────────────────┐
│ Authorization & Access Control           │
├──────────────────────────────────────────┤
│ Role-Based:                              │
│  ✓ super_admin: All data, all hospitals  │
│  ✓ hospital_admin: Hospital staff, wards │
│  ✓ doctor: Patients in hospital          │
│  ✓ nurse: Assigned ward patients         │
│  ✓ lab_technician: Lab orders assigned   │
│  ✓ receptionist: Scheduling only         │
│                                          │
│ Hospital-Scoped:                         │
│  ✓ Every query filtered by hospital_id   │
│  ✓ Create enforces hospital_id=user.hsp  │
│  ✓ Ward access limited to assigned ward  │
│                                          │
│ Cross-Facility:                          │
│  ✓ Consent scope: SUMMARY or FULL_RECORD │
│  ✓ Referral chain of trust               │
│  ✓ Break-glass 15-min window + audit     │
└──────────────────────────────────────────┘
```

### 3. Data Protection Layer

```
┌──────────────────────────────────────────┐
│ Data Protection                          │
├──────────────────────────────────────────┤
│ In Transit:                              │
│  ✓ TLS 1.3+ (HTTPS everywhere)           │
│  ✓ HSTS headers (enforce HTTPS)          │
│  ✓ Certificate pinning (optional)        │
│                                          │
│ At Rest (Production):                    │
│  ✓ PostgreSQL with SSL (Neon)            │
│  ✓ Encrypted fields (django-cryptography)│
│  ✓ S3 encryption for documents           │
│                                          │
│ Application:                             │
│  ✓ No PHI in logs (sanitized audit IDs) │
│  ✓ No credentials in config (env vars)   │
│  ✓ Secrets not in git (.gitignore)       │
└──────────────────────────────────────────┘
```

### 4. API Security Layer

```
┌──────────────────────────────────────────┐
│ API Security                             │
├──────────────────────────────────────────┤
│ Input Validation:                        │
│  ✓ DRF serializers (field validation)    │
│  ✓ Type checking (TypeScript frontend)   │
│  ✓ Reject oversized payloads (10 MB max) │
│                                          │
│ Output Encoding:                         │
│  ✓ JSON responses (not HTML)             │
│  ✓ Sanitized error messages              │
│  ✓ No stack traces in production         │
│                                          │
│ Rate Limiting:                           │
│  ✓ Per user: 200 req/hr (doctor)         │
│  ✓ Per IP: 1000 req/hr                   │
│  ✓ Brute-force: 10 login attempts/hr     │
│                                          │
│ CORS:                                    │
│  ✓ Whitelist allowed origins             │
│  ✓ Credentials: include only for same    │
│                                          │
│ CSRF:                                    │
│  ✓ JWT (not session cookies) immune      │
│  ✓ SameSite: Strict on any cookies       │
└──────────────────────────────────────────┘
```

### 5. Audit & Compliance Layer

```
┌──────────────────────────────────────────┐
│ Audit & Compliance (HIPAA/GDPR)          │
├──────────────────────────────────────────┤
│ Audit Logging:                           │
│  ✓ All CRUD actions: CREATE, UPDATE, etc │
│  ✓ Cross-facility views logged           │
│  ✓ Break-glass access fully logged       │
│  ✓ Authentication events (login, logout) │
│  ✓ Admin actions (staff changes, etc.)   │
│                                          │
│ Log Retention:                           │
│  ✓ 7 years (regulatory requirement)      │
│  ✓ Immutable once written                │
│  ✓ Indexed for compliance queries        │
│                                          │
│ Sanitization:                            │
│  ✓ resource_id never contains PHI        │
│  ✓ Details JSON has contextual data      │
│  ✓ Error messages don't expose internals  │
│                                          │
│ Compliance Reports:                      │
│  ✓ Daily break-glass review              │
│  ✓ Weekly access anomalies               │
│  ✓ Monthly cross-facility activity       │
└──────────────────────────────────────────┘
```

---

## Deployment Topology

### Architecture Diagram

```
                          INTERNET
                             |
                  ┌──────────┴──────────┐
                  |                     |
              [Vercel UI]         [Railway API]
              (Next.js Frontend)  (Django Backend)
              Hosted @ *.vercel.app  Hosted @ *.railway.app
                  |                     |
          ┌───────┴─────────┐    ┌──────┴──────┐
          │                 │    │             │
       [CDN]         [NextJS Build]  [API Routes]
       (Caching)    (Static Export)  (/api/v1/*)
          │             │           │
          └─────────────┴───────────┴──────────┐
                                               |
                        ┌──────────────────────┴──────┐
                        |                             |
                  [Neon PostgreSQL]       [Redis Cache]
                  (Managed DB)            (Sessions, Rate Limit)
                  (SSL required)          (Upstash Managed)
                        |                      |
                  ┌─────┴─────┐           ┌────┴────┐
                  │           │           │         │
              [Main DB] [Replica] [Session] [Rate Limit]
              (Read/Write) (Read-only)
```

### Deployment Environments

**Development (Local)**

```
Backend: Django dev server (localhost:8000)
  python manage.py runserver
  Uses SQLite or local PostgreSQL
  DEBUG=True, no MFA required

Frontend: Next.js dev server (localhost:3000)
  npm run dev
  Hot reload enabled
  E2E_* env vars set from .env.e2e

Testing: pytest + Playwright
  python -m pytest api/tests/
  npm run test:watch
```

**Staging (Railway)**

```
Backend Deployment:
  - Repository: linked to GitHub
  - Build: pip install -r requirements.txt
  - Entrypoint: gunicorn medsync_backend.wsgi:application --port $PORT
  - Env vars: DEBUG=False, SECRET_KEY, DATABASE_URL (Neon), etc.
  - Dyno type: standard (auto-scale 2-10 instances based on load)
  - Workers: Celery + Redis for background tasks

Database:
  - Neon PostgreSQL (managed)
  - Automatic daily backups
  - HA failover enabled
  - Point-in-time recovery (14 days)

Cache & Tasks:
  - Upstash Redis (managed)
  - Session store + rate limit tokens
  - Celery broker for background jobs

Frontend Deployment:
  - Separate Vercel project linked to GitHub
  - Root Directory: medsync-frontend/
  - Build: npm run build
  - Public URL: https://medsync-staging.vercel.app
  - Environment: NEXT_PUBLIC_API_URL=https://api-staging.railway.app/api/v1
```

**Production (Railway + Vercel)**

```
Backend (Railway):
  - Multiple dynos (minimum 3, auto-scale to 10+)
  - Managed SSL certificate
  - Load balancer (automatic)
  - Health checks: /api/v1/health (every 30s)
  - Graceful shutdown timeout: 30s
  - Logging: Railway logs + external (Papertrail, DataDog)

Database (Neon):
  - High-availability setup (primary + standby)
  - Automatic failover
  - Encryption at rest + in transit
  - Backup retention: 30 days
  - PITR: 7 days (for compliance restore)
  - Monitoring: Query performance, connections

Cache (Upstash):
  - Replicated Redis (HA)
  - Eviction policy: allkeys-lru (rate limit tokens)
  - Monitoring: Hit rate, latency

Frontend (Vercel):
  - Global CDN (auto-deploy from main branch)
  - HTTPS with automatic cert renewal
  - Custom domain: medsync.health (or customer domain)
  - Analytics: Performance metrics, error tracking
  - Caching: Aggressive for static assets, no-cache for dynamic

DNS & Routing:
  - API: api.medsync.health → Railway load balancer
  - UI: app.medsync.health → Vercel CDN

Monitoring & Alerts:
  - Uptime: 99.9% SLA (monitored by third party)
  - Response time: p95 < 2s
  - Error rate: < 0.5%
  - Alert channels: PagerDuty, Slack, email
```

### CI/CD Pipeline

```
GitHub Push → GitHub Actions
  ├─ Lint & Format
  │  ├─ Backend: flake8, black, isort (Python)
  │  └─ Frontend: eslint, prettier (TypeScript/React)
  │
  ├─ Test
  │  ├─ Backend: pytest (unit + integration)
  │  ├─ Frontend: vitest + Playwright E2E
  │  └─ Fail on coverage < 80%
  │
  ├─ Build
  │  ├─ Backend: Docker image (if using; optional for Railway)
  │  └─ Frontend: npm run build (verifies no warnings)
  │
  └─ Deploy (on main branch)
     ├─ Backend: Railway auto-deploys on push
     ├─ Frontend: Vercel auto-deploys on push
     └─ Post-deploy checks: /health endpoint, smoke tests
```

---

## Scalability Considerations

### Horizontal Scaling

**Backend (Django/API):**

- **Stateless servers:** Each instance has no local state; can be killed/added freely
- **Load balancer:** Railway/Vercel automatically distributes requests
- **Database:** PostgreSQL (Neon) handles connection pooling and replication
- **Cache:** Redis (Upstash) replicated across AZs for session and rate limit state

**Frontend (Next.js):**

- **Static export:** Generated HTML/JS cached globally on Vercel CDN
- **Edge functions:** Optional, for real-time data (ISR, on-demand revalidation)
- **No state:** Client-side state is temporary (memory) and resets per page load

### Database Optimization

```sql
-- Indexes for common queries
CREATE INDEX idx_patient_hospital ON patients(hospital_id);
CREATE INDEX idx_encounter_patient ON encounters(patient_id, created_at);
CREATE INDEX idx_audit_timestamp ON audit_logs(created_at);
CREATE INDEX idx_patient_admission_ward ON patient_admissions(ward_id, discharged_at);

-- Partitioning (for audit logs, after 1M rows)
-- PARTITION BY RANGE (YEAR(created_at))

-- Query optimization
-- Use cursor pagination for large result sets
-- Denormalize read-heavy views (e.g., latest vitals per patient)
```

### Caching Strategy

```
Layer 1: CDN (Vercel) — Static assets
  ├─ HTML: no-cache (dynamic per user)
  ├─ JS/CSS: max-age=31536000 (1 year, hash-based)
  └─ Images: max-age=2592000 (30 days)

Layer 2: Browser Cache
  └─ REST API responses: Cache-Control: private, max-age=300 (5 min)

Layer 3: Redis (Application Cache)
  ├─ Hospital list: 1 hour
  ├─ User permissions: 10 minutes (invalidated on role change)
  ├─ Patient summary (non-PHI): 5 minutes
  └─ Rate limit tokens: 1 hour (sliding window)
```

### Bottleneck Analysis & Mitigation

| Bottleneck | Symptom | Mitigation |
|-----------|---------|-----------|
| DB CPU | Slow queries | Add indexes, query optimization, read replicas |
| DB Connections | "too many connections" | Connection pooling, reduce query duration |
| Redis Memory | Eviction | Monitor hit rate, increase cache tier, adjust TTL |
| API Response Time | p95 > 2s | Caching, async processing (Celery), CDN |
| Frontend Load Time | > 3s | Code splitting, lazy loading, image optimization |

---

## References

- **HIPAA Security Rule:** 45 CFR §§ 164.308–164.318
- **GDPR:** Regulation (EU) 2016/679
- **HL7 FHIR:** https://www.hl7.org/fhir/
- **ICD-10-CM:** https://www.cms.gov/Medicare/Coding/ICD10
- **SNOMED CT:** https://www.snomed.org/

---

**For questions or updates, see:** docs/ directory in repository.
