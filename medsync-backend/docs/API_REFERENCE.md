# MedSync API Reference

**Base URL:** `http://localhost:8000/api/v1` (development) | Production: as deployed

**API Version:** v1

**Last Updated:** 2025

---

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Auth Endpoints](#auth-endpoints)
3. [Patient Management](#patient-management)
4. [Clinical Records](#clinical-records)
5. [Encounters & Visits](#encounters--visits)
6. [Appointments & Triage](#appointments--triage)
7. [Lab Management](#lab-management)
8. [Ward & Admissions](#ward--admissions)
9. [Shift Management](#shift-management)
10. [Cross-Facility Interop](#cross-facility-interop)
11. [AI Intelligence](#ai-intelligence)
12. [Admin & Governance](#admin--governance)
13. [Batch Operations](#batch-operations)
14. [Reporting & Analytics](#reporting--analytics)
15. [FHIR & HL7](#fhir--hl7)

---

## Authentication & Authorization

### Overview

MedSync uses JWT (JSON Web Token) with optional TOTP-based Multi-Factor Authentication (MFA). All API requests require authentication except those marked as `AllowAny`.

### Authentication Header

```
Authorization: Bearer <jwt_access_token>
```

### Token Lifecycle

- **Access Token TTL:** 15 minutes (configurable via `JWT_ACCESS_MINUTES`)
- **Refresh Token TTL:** 7 days
- **Token Type:** JWT with claims: `user_id`, `role`, `hospital_id`, `ward_id`

### Multi-Tenancy & Hospital Scoping

**Core principle:** Every user belongs to one hospital. All API responses are scoped to that hospital unless the user is a `super_admin` with no hospital assignment.

- **Regular Users (doctor, nurse, lab_technician, receptionist):** Can only view/create data for their assigned hospital
- **Hospital Admin:** Limited admin actions to their assigned hospital only
- **Super Admin:** Global access; optional `X-View-As-Hospital` header for auditing

### Role Matrix

| Endpoint Category | super_admin | hospital_admin | doctor | nurse | lab_technician | receptionist |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Patient Search & CRUD | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Clinical Records (Create) | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ |
| Prescriptions | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| Lab Orders | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| Lab Results | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ |
| Appointments | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Ward Management | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| User Admin | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Audit Logs | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| AI Features | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| Cross-Facility | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Break-Glass | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |

### Common HTTP Status Codes

- **200 OK** — Request succeeded
- **201 Created** — Resource created successfully
- **400 Bad Request** — Validation error (missing/invalid fields)
- **401 Unauthorized** — Missing/invalid authentication token
- **403 Forbidden** — Authenticated user lacks permission
- **404 Not Found** — Resource does not exist
- **429 Too Many Requests** — Rate limit exceeded
- **500 Internal Server Error** — Server-side error
- **503 Service Unavailable** — Database or critical service down

### Error Response Format

```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "details": {
    "field_name": ["Error message"]
  }
}
```

### Pagination

List endpoints support pagination via query parameters:

```
GET /api/v1/endpoint?limit=20&offset=0
```

Response includes:
```json
{
  "count": 150,
  "next": "...?limit=20&offset=20",
  "previous": null,
  "results": [...]
}
```

### Filtering & Ordering

- **Filter:** `?field=value` (e.g., `?status=active`)
- **Search:** `?search=term` (searches name, email, patient ID)
- **Ordering:** `?ordering=-created_at` (prefix with `-` for descending)

---

## Auth Endpoints

### 1. Login

**POST** `/auth/login`

**Permission:** AllowAny

**Description:** Initial login with email and password. Returns access/refresh tokens if successful. May trigger MFA requirement.

**Request Body:**
```json
{
  "email": "doctor@medsync.gh",
  "password": "SecurePass123!@#"
}
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "doctor@medsync.gh",
    "full_name": "Dr. Kwame",
    "role": "doctor",
    "hospital_id": "uuid",
    "hospital_name": "Korle-Bu Teaching Hospital",
    "mfa_enabled": true
  },
  "mfa_required": true,
  "mfa_method": "totp"
}
```

**Response (MFA Required - 200 OK):**
```json
{
  "mfa_required": true,
  "mfa_method": "totp",
  "session_id": "uuid"
}
```

**Error Cases:**
- `401`: Invalid email or password
- `400`: Missing required fields
- `429`: Account locked (too many failed attempts)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doctor@medsync.gh","password":"SecurePass123!@#"}'
```

---

### 2. MFA Verify (TOTP)

**POST** `/auth/mfa-verify`

**Permission:** AllowAny

**Description:** Verify TOTP code (6-digit authenticator app) for MFA.

**Request Body:**
```json
{
  "session_id": "uuid-from-login",
  "totp_code": "123456"
}
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "doctor@medsync.gh",
    "full_name": "Dr. Kwame",
    "role": "doctor",
    "hospital_id": "uuid",
    "hospital_name": "Korle-Bu Teaching Hospital"
  }
}
```

**Error Cases:**
- `400`: Invalid or expired TOTP code
- `429`: Too many MFA attempts (rate limited per user)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/mfa-verify \
  -H "Content-Type: application/json" \
  -d '{"session_id":"xxx","totp_code":"123456"}'
```

---

### 3. Refresh Token

**POST** `/auth/refresh`

**Permission:** AllowAny

**Description:** Exchange refresh token for new access token.

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Error Cases:**
- `401`: Invalid/expired/blacklisted refresh token

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh":"eyJ0eXA..."}'
```

---

### 4. Logout

**POST** `/auth/logout`

**Permission:** IsAuthenticated

**Description:** Revoke tokens and end session. Sends refresh token in body.

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

---

### 5. Get Current User

**GET** `/auth/me`

**Permission:** IsAuthenticated

**Description:** Retrieve authenticated user's profile and permissions.

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "doctor@medsync.gh",
  "full_name": "Dr. Kwame Adjei",
  "role": "doctor",
  "hospital_id": "uuid",
  "hospital_name": "Korle-Bu Teaching Hospital",
  "ward_id": "uuid",
  "ward_name": "Cardiology Ward",
  "is_active": true,
  "mfa_enabled": true,
  "account_status": "active"
}
```

**Example:**
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

### 6. Account Activation

**POST** `/auth/activate`

**Permission:** AllowAny

**Description:** Activate new account with temporary token and set permanent password.

**Request Body:**
```json
{
  "token": "temp-activation-token",
  "password": "NewSecurePass123!@#",
  "confirm_password": "NewSecurePass123!@#"
}
```

**Response (200 OK):**
```json
{
  "message": "Account activated successfully",
  "user": {
    "id": "uuid",
    "email": "doctor@medsync.gh",
    "account_status": "active"
  }
}
```

**Error Cases:**
- `400`: Password too weak (< 12 chars, missing uppercase/lowercase/digit/symbol)
- `400`: Token expired (> 24 hours old)

---

### 7. Forgot Password

**POST** `/auth/forgot-password`

**Permission:** AllowAny

**Description:** Request password reset link via email.

**Request Body:**
```json
{
  "email": "doctor@medsync.gh"
}
```

**Response (200 OK):**
```json
{
  "message": "If account exists, reset link sent to email"
}
```

**Note:** Generic response for security (prevents user enumeration).

---

### 8. Reset Password

**POST** `/auth/reset-password`

**Permission:** AllowAny

**Description:** Reset password with token from email.

**Request Body:**
```json
{
  "token": "reset-token-from-email",
  "password": "NewSecurePass123!@#",
  "confirm_password": "NewSecurePass123!@#"
}
```

**Response (200 OK):**
```json
{
  "message": "Password reset successfully"
}
```

---

### 9. Passkey Registration (Begin)

**POST** `/auth/passkey/register/begin`

**Permission:** IsAuthenticated

**Description:** Initiate WebAuthn/passkey registration.

**Response (200 OK):**
```json
{
  "options": {
    "challenge": "base64-encoded-challenge",
    "rp": {"name": "MedSync", "id": "medsync.gh"},
    "user": {"id": "uuid", "name": "doctor@medsync.gh", "displayName": "Dr. Kwame"},
    "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
    "timeout": 60000,
    "attestation": "none",
    "authenticatorSelection": {"residentKey": "preferred", "userVerification": "preferred"}
  }
}
```

---

### 10. Passkey Registration (Complete)

**POST** `/auth/passkey/register/complete`

**Permission:** IsAuthenticated

**Description:** Finalize WebAuthn/passkey registration with attestation.

**Request Body:**
```json
{
  "attestation_object": "base64-encoded",
  "client_data_json": "base64-encoded",
  "name": "My MacBook Pro"
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "name": "My MacBook Pro",
  "created_at": "2025-01-15T10:30:00Z",
  "last_used": null
}
```

---

### 11. List Passkeys

**GET** `/auth/passkeys`

**Permission:** IsAuthenticated

**Description:** List all registered passkeys for current user.

**Response (200 OK):**
```json
[
  {
    "id": "uuid",
    "name": "My MacBook Pro",
    "created_at": "2025-01-15T10:30:00Z",
    "last_used": "2025-01-20T14:22:00Z"
  }
]
```

---

### 12. Delete Passkey

**DELETE** `/auth/passkeys/<uuid:pk>`

**Permission:** IsAuthenticated

**Description:** Remove a registered passkey.

**Response (204 No Content)**

---

---

## Patient Management

### 1. Search Patients

**GET** `/patients/search`

**Permission:** IsAuthenticated

**Description:** Search patients by name, Ghana Health ID, NHIS number, phone. Results scoped to user's hospital (or all if super_admin).

**Query Parameters:**
```
?search=kwame&limit=20&offset=0&ordering=-created_at
```

**Response (200 OK):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "patient_id": "uuid",
      "ghana_health_id": "GHA-2024-001",
      "full_name": "Kwame Owusu",
      "date_of_birth": "1990-05-15",
      "gender": "M",
      "blood_group": "O+",
      "phone": "+233501234567",
      "national_id": "ABC123456789",
      "nhis_number": "NHIS-20250001",
      "registered_at": "uuid",
      "allergies": [
        {
          "allergy_id": "uuid",
          "allergen": "Penicillin",
          "reaction_type": "severe",
          "created_at": "2025-01-10T10:30:00Z"
        }
      ]
    }
  ]
}
```

**Required Role:** Any authenticated user

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/patients/search?search=kwame" \
  -H "Authorization: Bearer <access_token>"
```

---

### 2. Register New Patient

**POST** `/patients`

**Permission:** doctor, nurse, receptionist, hospital_admin, super_admin

**Description:** Register a new patient in the system. Assigns Ghana Health ID automatically.

**Request Body:**
```json
{
  "full_name": "Kwame Owusu",
  "date_of_birth": "1990-05-15",
  "gender": "M",
  "blood_group": "O+",
  "phone": "+233501234567",
  "national_id": "ABC123456789",
  "nhis_number": "NHIS-20250001",
  "passport_number": "P1234567",
  "address": "Accra, Ghana"
}
```

**Response (201 Created):**
```json
{
  "patient_id": "uuid",
  "ghana_health_id": "GHA-2025-00001",
  "full_name": "Kwame Owusu",
  "date_of_birth": "1990-05-15",
  "gender": "M",
  "blood_group": "O+",
  "phone": "+233501234567",
  "registered_at": "uuid",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Error Cases:**
- `400`: Missing required fields (full_name, date_of_birth, gender)
- `400`: Duplicate patient detected (exists by name + DOB)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Kwame Owusu",
    "date_of_birth": "1990-05-15",
    "gender": "M",
    "blood_group": "O+"
  }'
```

---

### 3. Get Patient Details

**GET** `/patients/<uuid:pk>`

**Permission:** IsAuthenticated

**Description:** Retrieve full patient profile including demographics, allergies, and cross-facility status.

**Response (200 OK):**
```json
{
  "patient_id": "uuid",
  "ghana_health_id": "GHA-2025-00001",
  "full_name": "Kwame Owusu",
  "date_of_birth": "1990-05-15",
  "gender": "M",
  "blood_group": "O+",
  "phone": "+233501234567",
  "national_id": "ABC123456789",
  "nhis_number": "NHIS-20250001",
  "registered_at": "uuid",
  "allergies": [],
  "global_patient_id": "uuid",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Error Cases:**
- `404`: Patient not found
- `403`: User's hospital differs from patient's hospital (unless cross-facility consent granted)

**Example:**
```bash
curl -X GET http://localhost:8000/api/v1/patients/<uuid> \
  -H "Authorization: Bearer <access_token>"
```

---

### 4. Patient Records Summary

**GET** `/patients/<uuid:pk>/records`

**Permission:** IsAuthenticated

**Description:** Get all clinical records (diagnoses, prescriptions, vitals, labs) for a patient.

**Query Parameters:**
```
?limit=50&offset=0&record_type=diagnosis
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "record_id": "uuid",
      "type": "diagnosis",
      "date_recorded": "2025-01-15T10:30:00Z",
      "details": {
        "icd10_code": "I10",
        "condition": "Essential hypertension",
        "status": "active"
      }
    }
  ]
}
```

---

### 5. Patient Diagnoses

**GET** `/patients/<uuid:pk>/diagnoses`

**Permission:** IsAuthenticated

**Description:** Retrieve all diagnoses for patient.

**Response (200 OK):**
```json
{
  "count": 3,
  "results": [
    {
      "diagnosis_id": "uuid",
      "icd10_code": "I10",
      "condition": "Essential hypertension",
      "status": "active",
      "date_diagnosed": "2024-12-01",
      "provider": "Dr. Kwame Adjei",
      "created_at": "2024-12-01T14:30:00Z"
    }
  ]
}
```

---

### 6. Patient Prescriptions

**GET** `/patients/<uuid:pk>/prescriptions`

**Permission:** IsAuthenticated

**Description:** Get all prescriptions (active & historical) for patient.

**Response (200 OK):**
```json
{
  "count": 8,
  "results": [
    {
      "prescription_id": "uuid",
      "drug_name": "Lisinopril",
      "dose": "10mg",
      "frequency": "Once daily",
      "duration": "30 days",
      "status": "active",
      "start_date": "2025-01-10",
      "prescribed_by": "Dr. Kwame Adjei",
      "created_at": "2025-01-10T10:30:00Z"
    }
  ]
}
```

---

### 7. Patient Labs

**GET** `/patients/<uuid:pk>/labs`

**Permission:** IsAuthenticated

**Description:** Retrieve lab orders and results for patient.

**Response (200 OK):**
```json
{
  "count": 5,
  "results": [
    {
      "lab_order_id": "uuid",
      "test_name": "Full Blood Count",
      "ordered_date": "2025-01-15",
      "status": "completed",
      "result": {
        "hemoglobin": "13.5 g/dL",
        "wbc": "7.2 K/uL",
        "platelets": "250 K/uL"
      },
      "completed_date": "2025-01-16T09:30:00Z"
    }
  ]
}
```

---

### 8. Patient Vitals

**GET** `/patients/<uuid:pk>/vitals`

**Permission:** IsAuthenticated

**Description:** Get vital signs history (last 30 days).

**Response (200 OK):**
```json
{
  "count": 28,
  "results": [
    {
      "vital_id": "uuid",
      "temperature": 37.1,
      "systolic_bp": 120,
      "diastolic_bp": 80,
      "heart_rate": 72,
      "respiratory_rate": 16,
      "oxygen_saturation": 98.5,
      "blood_glucose": 95,
      "recorded_at": "2025-01-15T10:30:00Z",
      "recorded_by": "Nurse Akosua"
    }
  ]
}
```

---

### 9. Export Patient to PDF

**GET** `/patients/<uuid:pk>/export-pdf`

**Permission:** IsAuthenticated

**Description:** Generate and download patient medical record as PDF.

**Response:** PDF binary file

**Example:**
```bash
curl -X GET http://localhost:8000/api/v1/patients/<uuid>/export-pdf \
  -H "Authorization: Bearer <access_token>" \
  --output patient_record.pdf
```

---

---

## Clinical Records

### 1. Create Diagnosis

**POST** `/records/diagnosis`

**Permission:** doctor

**Description:** Add diagnosis (ICD-10) for a patient in an encounter.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "encounter_id": "uuid",
  "icd10_code": "I10",
  "condition_name": "Essential hypertension",
  "status": "active",
  "notes": "Patient on lisinopril, BP controlled"
}
```

**Response (201 Created):**
```json
{
  "diagnosis_id": "uuid",
  "patient_id": "uuid",
  "icd10_code": "I10",
  "condition_name": "Essential hypertension",
  "status": "active",
  "date_diagnosed": "2025-01-15",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Error Cases:**
- `400`: Invalid ICD-10 code
- `403`: Doctor not assigned to patient's hospital
- `404`: Patient or encounter not found

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/records/diagnosis \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "uuid",
    "encounter_id": "uuid",
    "icd10_code": "I10",
    "condition_name": "Essential hypertension",
    "status": "active"
  }'
```

---

### 2. ICD-10 Autocomplete

**GET** `/records/icd10-autocomplete`

**Permission:** IsAuthenticated

**Description:** Search ICD-10 codes for diagnosis entry.

**Query Parameters:**
```
?search=hypertension&limit=10
```

**Response (200 OK):**
```json
[
  {
    "code": "I10",
    "name": "Essential (primary) hypertension",
    "category": "Diseases of the circulatory system"
  },
  {
    "code": "I11",
    "name": "Hypertensive heart disease",
    "category": "Diseases of the circulatory system"
  }
]
```

---

### 3. Create Prescription

**POST** `/records/prescription`

**Permission:** doctor

**Description:** Write prescription for patient.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "encounter_id": "uuid",
  "drug_name": "Lisinopril",
  "drug_code": "C09AA01",
  "dose": "10",
  "dose_unit": "mg",
  "frequency": "Once daily",
  "route": "Oral",
  "duration": "30",
  "duration_unit": "days",
  "quantity": 30,
  "refills": 2,
  "indication": "Hypertension management",
  "notes": "Take with food if nausea occurs"
}
```

**Response (201 Created):**
```json
{
  "prescription_id": "uuid",
  "patient_id": "uuid",
  "drug_name": "Lisinopril",
  "dose": "10mg",
  "frequency": "Once daily",
  "status": "active",
  "start_date": "2025-01-15",
  "end_date": "2025-02-14",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 4. Dispense Prescription

**POST** `/records/prescription/<uuid:record_id>/dispense`

**Permission:** pharmacist (via pharmacy worklist)

**Description:** Mark prescription as dispensed by pharmacy.

**Request Body:**
```json
{
  "quantity_dispensed": 30,
  "batch_number": "BATCH-2025-001",
  "expiry_date": "2026-01-15",
  "notes": "Counseled patient on side effects"
}
```

**Response (200 OK):**
```json
{
  "prescription_id": "uuid",
  "status": "dispensed",
  "quantity_dispensed": 30,
  "dispensed_at": "2025-01-15T11:00:00Z",
  "dispensed_by": "Pharmacy Technician"
}
```

---

### 5. Create Lab Order

**POST** `/records/lab-order`

**Permission:** doctor

**Description:** Place laboratory test order for patient.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "encounter_id": "uuid",
  "test_type": "Full Blood Count",
  "test_code": "CBC",
  "priority": "routine",
  "clinical_indication": "Routine checkup",
  "notes": "Fasting not required"
}
```

**Response (201 Created):**
```json
{
  "lab_order_id": "uuid",
  "patient_id": "uuid",
  "test_name": "Full Blood Count",
  "status": "pending",
  "ordered_date": "2025-01-15",
  "priority": "routine",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 6. Create Vitals

**POST** `/records/vitals`

**Permission:** nurse, doctor

**Description:** Record patient vital signs during encounter.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "encounter_id": "uuid",
  "temperature": 37.2,
  "systolic_bp": 120,
  "diastolic_bp": 80,
  "heart_rate": 72,
  "respiratory_rate": 16,
  "oxygen_saturation": 98.5,
  "blood_glucose": 95,
  "recorded_at": "2025-01-15T10:30:00Z"
}
```

**Response (201 Created):**
```json
{
  "vital_id": "uuid",
  "patient_id": "uuid",
  "temperature": 37.2,
  "systolic_bp": 120,
  "diastolic_bp": 80,
  "recorded_at": "2025-01-15T10:30:00Z",
  "recorded_by": "Nurse Akosua"
}
```

---

### 7. Batch Create Vitals

**POST** `/records/vitals/batch`

**Permission:** nurse

**Description:** Record vitals for multiple patients at once (e.g., end of shift).

**Request Body:**
```json
{
  "vitals": [
    {
      "patient_id": "uuid1",
      "encounter_id": "uuid1",
      "temperature": 37.0,
      "systolic_bp": 120,
      "diastolic_bp": 80,
      "heart_rate": 70
    },
    {
      "patient_id": "uuid2",
      "encounter_id": "uuid2",
      "temperature": 37.5,
      "systolic_bp": 130,
      "diastolic_bp": 85,
      "heart_rate": 75
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "created": 2,
  "failed": 0,
  "results": [
    {
      "vital_id": "uuid1",
      "status": "success"
    }
  ]
}
```

---

### 8. Create Nursing Note

**POST** `/records/nursing-note`

**Permission:** nurse

**Description:** Document nursing observations and care activities.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "encounter_id": "uuid",
  "note": "Patient alert and oriented. Pain well-controlled on current medication. Eating and drinking well.",
  "category": "shift_note"
}
```

**Response (201 Created):**
```json
{
  "note_id": "uuid",
  "patient_id": "uuid",
  "note_type": "nursing_note",
  "category": "shift_note",
  "created_at": "2025-01-15T10:30:00Z",
  "created_by": "Nurse Akosua"
}
```

---

### 9. Create Allergy Record

**POST** `/records/allergy`

**Permission:** doctor, nurse, receptionist

**Description:** Document patient allergy.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "allergen": "Penicillin",
  "reaction_type": "severe",
  "reaction_description": "Anaphylaxis - swelling, difficulty breathing",
  "onset_date": "2015-03-20"
}
```

**Response (201 Created):**
```json
{
  "allergy_id": "uuid",
  "allergen": "Penicillin",
  "reaction_type": "severe",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 10. Amend Medical Record

**POST** `/records/<uuid:record_id>/amend`

**Permission:** doctor (only own records; super_admin can amend any)

**Description:** Add amendment/correction to existing clinical record (e.g., dosage correction). Original record preserved in audit log.

**Request Body:**
```json
{
  "amendment_reason": "Dosage correction - was 10mg, should be 20mg",
  "amended_field": "dose",
  "new_value": "20mg",
  "old_value": "10mg"
}
```

**Response (200 OK):**
```json
{
  "record_id": "uuid",
  "amendment_id": "uuid",
  "amended_at": "2025-01-15T10:45:00Z",
  "amended_by": "Dr. Kwame Adjei",
  "amendment_reason": "Dosage correction - was 10mg, should be 20mg"
}
```

---

### 11. Medication Schedule

**GET** `/ward/medication-schedule`

**Permission:** nurse

**Description:** Get all medications due for ward's patients in next 24 hours.

**Query Parameters:**
```
?ward_id=uuid&limit=50
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "schedule_id": "uuid",
      "patient_name": "Kwame Owusu",
      "patient_id": "uuid",
      "drug_name": "Lisinopril",
      "dose": "10mg",
      "frequency": "Once daily",
      "due_time": "2025-01-15T08:00:00Z",
      "status": "pending",
      "bed_number": "A-102",
      "notes": "With breakfast"
    }
  ]
}
```

---

### 12. Administer Medication

**POST** `/prescriptions/<uuid:prescription_id>/administer`

**Permission:** nurse

**Description:** Record medication administration (MAR - Medication Administration Record).

**Request Body:**
```json
{
  "administered_at": "2025-01-15T08:15:00Z",
  "administered_by_id": "uuid",
  "notes": "Patient took medication without issue"
}
```

**Response (200 OK):**
```json
{
  "schedule_id": "uuid",
  "status": "administered",
  "administered_at": "2025-01-15T08:15:00Z",
  "administered_by": "Nurse Akosua"
}
```

---

---

## Encounters & Visits

### 1. List Encounters

**GET** `/patients/<uuid:pk>/encounters`

**Permission:** IsAuthenticated

**Description:** Get all encounters for a patient (ongoing + historical).

**Query Parameters:**
```
?status=ongoing&limit=20&offset=0
```

**Response (200 OK):**
```json
{
  "count": 15,
  "results": [
    {
      "encounter_id": "uuid",
      "patient_id": "uuid",
      "encounter_type": "outpatient",
      "status": "ongoing",
      "start_time": "2025-01-15T10:00:00Z",
      "end_time": null,
      "chief_complaint": "Hypertension follow-up",
      "provider": "Dr. Kwame Adjei",
      "location": "Cardiology Clinic"
    }
  ]
}
```

---

### 2. Get Encounter Details

**GET** `/patients/<uuid:pk>/encounters/<uuid:encounter_id>`

**Permission:** IsAuthenticated

**Description:** Retrieve full encounter with all clinical data.

**Response (200 OK):**
```json
{
  "encounter_id": "uuid",
  "patient_id": "uuid",
  "encounter_type": "outpatient",
  "status": "ongoing",
  "start_time": "2025-01-15T10:00:00Z",
  "end_time": null,
  "chief_complaint": "Hypertension follow-up",
  "provider_id": "uuid",
  "provider_name": "Dr. Kwame Adjei",
  "location": "Cardiology Clinic",
  "diagnoses": [
    {
      "icd10_code": "I10",
      "condition": "Essential hypertension",
      "status": "active"
    }
  ],
  "prescriptions": [...],
  "vitals": [...],
  "lab_orders": [...]
}
```

---

### 3. Close Encounter

**POST** `/patients/<uuid:pk>/encounters/<uuid:encounter_id>/close`

**Permission:** doctor

**Description:** End encounter and lock all associated records.

**Request Body:**
```json
{
  "summary": "Patient BP well-controlled. Continue current medications.",
  "follow_up_plan": "Follow-up in 1 month"
}
```

**Response (200 OK):**
```json
{
  "encounter_id": "uuid",
  "status": "closed",
  "end_time": "2025-01-15T11:30:00Z",
  "summary": "Patient BP well-controlled. Continue current medications."
}
```

---

### 4. Encounter Draft

**GET/POST** `/patients/<uuid:pk>/draft`

**Permission:** doctor

**Description:** Auto-save encounter draft (prevents data loss). GET retrieves latest draft; POST creates/updates draft.

**POST Request Body:**
```json
{
  "chief_complaint": "Follow-up hypertension",
  "chief_complaint_duration": "ongoing",
  "findings": "BP 120/80, pulse 72",
  "assessment": "Hypertension well controlled",
  "plan": "Continue lisinopril"
}
```

**Response (200 OK):**
```json
{
  "draft_id": "uuid",
  "patient_id": "uuid",
  "auto_saved_at": "2025-01-15T10:45:00Z",
  "data": {...}
}
```

---

### 5. Worklist Encounters

**GET** `/worklist/encounters`

**Permission:** doctor, nurse

**Description:** Get encounters requiring action (pending signatures, incomplete records, etc.).

**Query Parameters:**
```
?filter=pending_review&limit=20
```

**Response (200 OK):**
```json
{
  "count": 8,
  "pending_review": 3,
  "pending_signature": 5,
  "results": [
    {
      "encounter_id": "uuid",
      "patient_name": "Kwame Owusu",
      "status": "pending_review",
      "action_required": "Review and close encounter",
      "time_pending": "2 hours"
    }
  ]
}
```

---

### 6. Encounter Templates

**GET** `/encounter-templates`

**Permission:** IsAuthenticated

**Description:** List available encounter templates (e.g., "HypertensionFollow-up", "PostOp CheckIn").

**Response (200 OK):**
```json
[
  {
    "template_id": "uuid",
    "name": "Hypertension Follow-up",
    "description": "Standard hypertension management template",
    "fields": ["chief_complaint", "BP", "medication_adherence", "follow_up_date"],
    "created_by": "Dr. Admin"
  }
]
```

---

### 7. Apply Encounter Template

**POST** `/patients/<uuid:patient_pk>/encounters/<uuid:encounter_id>/apply-template/<uuid:template_id>`

**Permission:** doctor

**Description:** Populate encounter with template's standard fields.

**Response (200 OK):**
```json
{
  "encounter_id": "uuid",
  "template_applied": "Hypertension Follow-up",
  "fields_populated": 5,
  "message": "Template applied successfully"
}
```

---

---

## Appointments & Triage

### 1. List Appointments

**GET** `/appointments`

**Permission:** IsAuthenticated

**Description:** Get appointments for current user's department/ward.

**Query Parameters:**
```
?date=2025-01-15&status=scheduled&doctor_id=uuid&limit=20
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "appointment_id": "uuid",
      "patient_id": "uuid",
      "patient_name": "Kwame Owusu",
      "appointment_datetime": "2025-01-15T10:00:00Z",
      "status": "scheduled",
      "appointment_type": "follow-up",
      "doctor_id": "uuid",
      "doctor_name": "Dr. Kwame Adjei",
      "department": "Cardiology",
      "duration_minutes": 30
    }
  ]
}
```

---

### 2. Create Appointment

**POST** `/appointments/create`

**Permission:** receptionist, doctor, hospital_admin

**Description:** Schedule new appointment for patient with doctor.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "doctor_id": "uuid",
  "appointment_datetime": "2025-01-20T14:00:00Z",
  "appointment_type": "follow-up",
  "duration_minutes": 30,
  "notes": "Hypertension follow-up",
  "is_walk_in": false
}
```

**Response (201 Created):**
```json
{
  "appointment_id": "uuid",
  "patient_id": "uuid",
  "appointment_datetime": "2025-01-20T14:00:00Z",
  "status": "scheduled",
  "confirmation_number": "APT-20250120-001",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 3. Check Doctor Availability

**GET** `/doctors/<uuid:doctor_id>/availability`

**Permission:** receptionist, hospital_admin

**Description:** Check doctor's available time slots.

**Query Parameters:**
```
?date=2025-01-20&duration_minutes=30
```

**Response (200 OK):**
```json
{
  "doctor_name": "Dr. Kwame Adjei",
  "date": "2025-01-20",
  "available_slots": [
    "09:00:00",
    "09:30:00",
    "10:00:00",
    "14:00:00",
    "14:30:00"
  ],
  "booked_slots": ["11:00:00", "15:00:00"]
}
```

---

### 4. Create Walk-In

**POST** `/appointments/walk-in`

**Permission:** receptionist

**Description:** Register walk-in patient without prior appointment.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "department_id": "uuid",
  "chief_complaint": "Acute fever",
  "triage_priority": "urgent",
  "notes": "3 days fever, high temp"
}
```

**Response (201 Created):**
```json
{
  "appointment_id": "uuid",
  "patient_id": "uuid",
  "status": "walk_in",
  "queue_position": 3,
  "wait_time_estimate": "45 minutes",
  "created_at": "2025-01-15T14:30:00Z"
}
```

---

### 5. Walk-In Queue

**GET** `/appointments/walk-in-queue`

**Permission:** receptionist, nurse

**Description:** Get current walk-in queue for triage/waiting area.

**Query Parameters:**
```
?ward_id=uuid
```

**Response (200 OK):**
```json
{
  "queue_length": 5,
  "total_wait_time_avg": 45,
  "results": [
    {
      "appointment_id": "uuid",
      "patient_name": "Kwame Owusu",
      "queue_position": 1,
      "chief_complaint": "Acute fever",
      "triage_priority": "urgent",
      "wait_time": "35 minutes",
      "status": "waiting"
    }
  ]
}
```

---

### 6. Check In Appointment

**POST** `/appointments/<uuid:pk>/check-in`

**Permission:** receptionist, nurse

**Description:** Mark patient as arrived and checked in.

**Request Body:**
```json
{
  "checked_in_by": "uuid"
}
```

**Response (200 OK):**
```json
{
  "appointment_id": "uuid",
  "status": "checked_in",
  "checked_in_at": "2025-01-15T14:35:00Z",
  "wait_time_so_far": 5
}
```

---

### 7. Triage Assignment

**POST** `/emergency/triage/<uuid:appointment_id>`

**Permission:** nurse, doctor

**Description:** Assign triage color (red/yellow/green) based on ESI protocol.

**Request Body:**
```json
{
  "triage_color": "yellow",
  "vital_signs": {
    "systolic_bp": 145,
    "diastolic_bp": 95,
    "heart_rate": 110,
    "temperature": 39.5,
    "respiratory_rate": 22
  },
  "assessment": "Fever, elevated vitals, stable but needs urgent evaluation",
  "assigned_to_doctor_id": "uuid"
}
```

**Response (200 OK):**
```json
{
  "appointment_id": "uuid",
  "triage_color": "yellow",
  "triage_priority": "urgent",
  "assigned_to": "Dr. Kwame Adjei",
  "assigned_at": "2025-01-15T14:40:00Z"
}
```

---

### 8. ED Queue Real-Time

**GET** `/emergency/queue`

**Permission:** nurse, doctor

**Description:** Live emergency department queue status.

**Response (200 OK):**
```json
{
  "total_waiting": 8,
  "by_color": {
    "red": 1,
    "yellow": 3,
    "green": 4
  },
  "average_wait_time": 35,
  "queue": [
    {
      "appointment_id": "uuid",
      "patient_name": "Kwame Owusu",
      "triage_color": "red",
      "wait_time": 15,
      "status": "being_seen"
    }
  ]
}
```

---

---

## Lab Management

### 1. List Lab Orders

**GET** `/lab/orders`

**Permission:** lab_technician, doctor

**Description:** Get lab orders (pending, completed, cancelled).

**Query Parameters:**
```
?status=pending&limit=20&ordering=-created_at
```

**Response (200 OK):**
```json
{
  "count": 15,
  "results": [
    {
      "lab_order_id": "uuid",
      "patient_id": "uuid",
      "patient_name": "Kwame Owusu",
      "test_name": "Full Blood Count",
      "status": "pending",
      "ordered_date": "2025-01-15",
      "priority": "routine",
      "ordered_by": "Dr. Kwame Adjei",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

### 2. Get Lab Order Detail

**GET** `/lab/orders/<uuid:order_id>`

**Permission:** lab_technician, doctor

**Description:** Retrieve full lab order with test parameters and current status.

**Response (200 OK):**
```json
{
  "lab_order_id": "uuid",
  "patient_id": "uuid",
  "patient_name": "Kwame Owusu",
  "test_name": "Full Blood Count",
  "test_code": "CBC",
  "status": "in_progress",
  "priority": "routine",
  "ordered_date": "2025-01-15",
  "ordered_by": "Dr. Kwame Adjei",
  "clinical_indication": "Routine checkup",
  "sample_collected": true,
  "sample_collection_time": "2025-01-15T10:45:00Z"
}
```

---

### 3. Submit Lab Result

**POST** `/lab/orders/<uuid:order_id>/result`

**Permission:** lab_technician

**Description:** Enter lab test results.

**Request Body:**
```json
{
  "results": {
    "hemoglobin": "13.5 g/dL",
    "hematocrit": "41%",
    "wbc": "7.2 K/uL",
    "platelets": "250 K/uL",
    "mcv": "88 fL"
  },
  "reference_ranges": {
    "hemoglobin": "13.5-17.5",
    "wbc": "4.5-11"
  },
  "notes": "All values within normal range",
  "completed_at": "2025-01-16T09:30:00Z"
}
```

**Response (200 OK):**
```json
{
  "lab_order_id": "uuid",
  "status": "completed",
  "results": {...},
  "completed_at": "2025-01-16T09:30:00Z",
  "verified_by": "Lab Technician Ama",
  "result_id": "uuid"
}
```

---

### 4. Bulk Submit Results

**POST** `/lab/results/bulk-submit`

**Permission:** lab_technician

**Description:** Submit multiple lab results at once.

**Request Body:**
```json
{
  "results": [
    {
      "lab_order_id": "uuid1",
      "results": {"hemoglobin": "13.5 g/dL", ...},
      "completed_at": "2025-01-16T09:30:00Z"
    },
    {
      "lab_order_id": "uuid2",
      "results": {"glucose": "95 mg/dL", ...},
      "completed_at": "2025-01-16T09:35:00Z"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "submitted": 2,
  "failed": 0,
  "results": [
    {
      "lab_order_id": "uuid1",
      "status": "success"
    }
  ]
}
```

---

### 5. Lab Analytics Trends

**GET** `/lab/analytics/trends`

**Permission:** lab_technician, hospital_admin

**Description:** Get lab result trends (e.g., abnormal result frequency by test).

**Query Parameters:**
```
?start_date=2025-01-01&end_date=2025-01-15&test_type=CBC
```

**Response (200 OK):**
```json
{
  "period": "2025-01-01 to 2025-01-15",
  "total_tests": 150,
  "by_test": {
    "CBC": {
      "count": 50,
      "abnormal_results": 5,
      "abnormal_rate": "10%"
    }
  }
}
```

---

---

## Ward & Admissions

### 1. List Admissions

**GET** `/admissions`

**Permission:** nurse, doctor, hospital_admin

**Description:** Get active and past admissions.

**Query Parameters:**
```
?status=active&ward_id=uuid&limit=20
```

**Response (200 OK):**
```json
{
  "count": 8,
  "results": [
    {
      "admission_id": "uuid",
      "patient_id": "uuid",
      "patient_name": "Kwame Owusu",
      "admission_date": "2025-01-14",
      "status": "active",
      "ward_id": "uuid",
      "ward_name": "Cardiology",
      "bed_number": "A-102",
      "admitted_by": "Dr. Kwame Adjei",
      "discharge_date": null,
      "length_of_stay_days": 1
    }
  ]
}
```

---

### 2. Create Admission

**POST** `/admissions/create`

**Permission:** doctor

**Description:** Admit patient to ward/bed.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "ward_id": "uuid",
  "bed_id": "uuid",
  "admission_reason": "Acute hypertensive crisis",
  "medical_officer_name": "Dr. Kwame Adjei",
  "medical_officer_license": "GHA/2020/1234",
  "admission_notes": "BP 180/110, requiring close monitoring"
}
```

**Response (201 Created):**
```json
{
  "admission_id": "uuid",
  "patient_id": "uuid",
  "ward_id": "uuid",
  "bed_number": "A-102",
  "admission_date": "2025-01-15T10:30:00Z",
  "status": "active",
  "admission_number": "ADM-20250115-001"
}
```

---

### 3. Admissions by Ward

**GET** `/admissions/ward/<uuid:ward_id>`

**Permission:** nurse, doctor

**Description:** Get all admissions in specific ward.

**Response (200 OK):**
```json
{
  "ward_name": "Cardiology",
  "total_beds": 20,
  "occupied_beds": 15,
  "occupancy_rate": "75%",
  "admissions": [...]
}
```

---

### 4. Discharge Patient

**POST** `/admissions/<uuid:admission_id>/discharge`

**Permission:** doctor

**Description:** End patient admission and free bed.

**Request Body:**
```json
{
  "discharge_reason": "Clinical recovery - stable for home",
  "discharge_notes": "Continue current medications. Follow-up in 1 week.",
  "discharge_date": "2025-01-16",
  "discharge_destination": "Home",
  "discharged_by": "uuid"
}
```

**Response (200 OK):**
```json
{
  "admission_id": "uuid",
  "status": "discharged",
  "discharge_date": "2025-01-16T10:30:00Z",
  "length_of_stay_days": 2,
  "discharge_summary_url": "/api/v1/admissions/uuid/discharge-summary"
}
```

---

### 5. Ward List

**GET** `/admin/wards`

**Permission:** hospital_admin, super_admin

**Description:** Get all wards in hospital.

**Response (200 OK):**
```json
{
  "count": 8,
  "results": [
    {
      "ward_id": "uuid",
      "ward_name": "Cardiology",
      "department": "Internal Medicine",
      "total_beds": 20,
      "occupied_beds": 15,
      "ward_manager": "Nurse Ama Kwarteng"
    }
  ]
}
```

---

### 6. Create Ward

**POST** `/admin/wards/create`

**Permission:** hospital_admin, super_admin

**Description:** Create new ward.

**Request Body:**
```json
{
  "ward_name": "Intensive Care Unit",
  "department_id": "uuid",
  "total_beds": 10,
  "ward_manager_id": "uuid",
  "description": "ICU with monitoring equipment"
}
```

**Response (201 Created):**
```json
{
  "ward_id": "uuid",
  "ward_name": "Intensive Care Unit",
  "total_beds": 10,
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 7. Create Beds (Bulk)

**POST** `/admin/wards/<uuid:ward_id>/beds/bulk`

**Permission:** hospital_admin, super_admin

**Description:** Add multiple beds to ward at once.

**Request Body:**
```json
{
  "bed_count": 5,
  "bed_prefix": "A",
  "starting_number": 100,
  "bed_type": "standard"
}
```

**Response (201 Created):**
```json
{
  "created": 5,
  "beds": [
    {
      "bed_id": "uuid",
      "bed_number": "A-100",
      "status": "available"
    },
    {
      "bed_id": "uuid",
      "bed_number": "A-101",
      "status": "available"
    }
  ]
}
```

---

---

## Shift Management

### 1. Start Shift

**POST** `/shifts/start`

**Permission:** doctor, nurse, lab_technician

**Description:** Clock in for shift.

**Request Body:**
```json
{
  "shift_date": "2025-01-15",
  "start_time": "2025-01-15T08:00:00Z",
  "ward_id": "uuid",
  "location": "Cardiology Ward"
}
```

**Response (201 Created):**
```json
{
  "shift_id": "uuid",
  "staff_name": "Nurse Akosua",
  "shift_date": "2025-01-15",
  "start_time": "2025-01-15T08:00:00Z",
  "status": "active",
  "shift_duration_hours": 12
}
```

---

### 2. End Shift

**POST** `/shifts/<uuid:shift_id>/end`

**Permission:** doctor, nurse (own shift only)

**Description:** Clock out from shift.

**Request Body:**
```json
{
  "end_time": "2025-01-15T20:00:00Z",
  "end_notes": "Uneventful shift. All patients stable."
}
```

**Response (200 OK):**
```json
{
  "shift_id": "uuid",
  "status": "completed",
  "end_time": "2025-01-15T20:00:00Z",
  "duration_hours": 12,
  "handover_required": true
}
```

---

### 3. Shift Handover

**POST** `/shifts/<uuid:shift_id>/handover`

**Permission:** doctor, nurse (outgoing staff)

**Description:** Document handover to next shift staff.

**Request Body:**
```json
{
  "handover_notes": "3 critical patients: Bed A-102 (post-op cardiac), A-105 (acute MI monitoring), A-110 (ICU)",
  "critical_alerts": [
    {"patient_id": "uuid", "alert": "Allergic to Penicillin - order alternatives"}
  ],
  "pending_actions": [
    {"patient_id": "uuid", "action": "Lab results pending - check at 14:00"}
  ],
  "handed_over_to_id": "uuid"
}
```

**Response (201 Created):**
```json
{
  "handover_id": "uuid",
  "shift_id": "uuid",
  "handed_over_at": "2025-01-15T20:00:00Z",
  "handed_over_by": "Nurse Akosua",
  "status": "pending_acknowledgment"
}
```

---

### 4. Acknowledge Handover

**POST** `/nurse/shift-handover/<uuid:handover_id>/acknowledge`

**Permission:** nurse (incoming staff)

**Description:** Acknowledge receipt of handover and accept responsibility.

**Request Body:**
```json
{
  "acknowledged_at": "2025-01-15T20:05:00Z",
  "confirmation_notes": "Reviewed all critical alerts. Understood and ready."
}
```

**Response (200 OK):**
```json
{
  "handover_id": "uuid",
  "acknowledged_at": "2025-01-15T20:05:00Z",
  "acknowledged_by": "Nurse Ama",
  "status": "acknowledged"
}
```

---

### 5. Current Shift

**GET** `/shifts/current`

**Permission:** doctor, nurse

**Description:** Get current active shift (if any).

**Response (200 OK):**
```json
{
  "shift_id": "uuid",
  "status": "active",
  "start_time": "2025-01-15T08:00:00Z",
  "elapsed_hours": 6,
  "ward_id": "uuid",
  "ward_name": "Cardiology Ward"
}
```

---

### 6. Shift Statistics

**GET** `/shifts/<uuid:shift_id>/statistics`

**Permission:** nurse, hospital_admin

**Description:** Get shift metrics (patients seen, procedures, incidents).

**Response (200 OK):**
```json
{
  "shift_id": "uuid",
  "patients_admitted": 3,
  "patients_discharged": 2,
  "vitals_recorded": 25,
  "medications_administered": 18,
  "incidents_reported": 0,
  "average_wait_time": 15
}
```

---

---

## Cross-Facility Interop

### 1. Global Patient Search

**GET** `/global-patients/search`

**Permission:** doctor, hospital_admin

**Description:** Search for patients across all hospitals (by Ghana Health ID or GPID).

**Query Parameters:**
```
?search=GHA-2024-001&limit=10
```

**Response (200 OK):**
```json
[
  {
    "global_patient_id": "uuid",
    "ghana_health_id": "GHA-2024-001",
    "full_name": "Kwame Owusu",
    "facilities": [
      {
        "facility_id": "uuid",
        "facility_name": "Korle-Bu Teaching Hospital",
        "patient_at_facility_id": "uuid",
        "date_first_seen": "2024-08-15",
        "consent_status": "not_requested"
      },
      {
        "facility_id": "uuid",
        "facility_name": "Ridge Regional Hospital",
        "patient_at_facility_id": "uuid",
        "date_first_seen": "2025-01-10",
        "consent_status": "granted"
      }
    ]
  }
]
```

---

### 2. Link Facility Patients

**POST** `/facility-patients/link`

**Permission:** super_admin, hospital_admin

**Description:** Link patients from different hospitals to same global patient.

**Request Body:**
```json
{
  "global_patient_id": "uuid",
  "facility_patient_ids": ["uuid1", "uuid2"]
}
```

**Response (200 OK):**
```json
{
  "global_patient_id": "uuid",
  "linked_patients": 2,
  "message": "Patients linked successfully"
}
```

---

### 3. Consent - Grant Access

**POST** `/consents`

**Permission:** hospital_admin (grantor hospital)

**Description:** Grant access to patient records from another facility.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "requesting_facility_id": "uuid",
  "scope": "FULL_RECORD",
  "expiration_days": 90,
  "reason": "Patient referred to our facility for cardiology evaluation"
}
```

**Response (201 Created):**
```json
{
  "consent_id": "uuid",
  "patient_id": "uuid",
  "grantor_facility": "Korle-Bu Teaching Hospital",
  "requesting_facility": "Ridge Regional Hospital",
  "scope": "FULL_RECORD",
  "status": "granted",
  "granted_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-04-15T10:30:00Z"
}
```

---

### 4. List Consents

**GET** `/consents/list`

**Permission:** hospital_admin

**Description:** Get all consent records for hospital.

**Query Parameters:**
```
?status=granted&limit=20
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [...]
}
```

---

### 5. Revoke Consent

**DELETE** `/consents/<uuid:pk>`

**Permission:** hospital_admin (grantor hospital)

**Description:** Withdraw consent and revoke access.

**Response (204 No Content)**

---

### 6. Create Referral

**POST** `/referrals`

**Permission:** doctor

**Description:** Refer patient to another facility.

**Request Body:**
```json
{
  "patient_id": "uuid",
  "referring_facility_id": "uuid",
  "receiving_facility_id": "uuid",
  "referring_doctor_id": "uuid",
  "chief_complaint": "Persistent fever unresponsive to antibiotics",
  "clinical_summary": "3-week fever, workup inconclusive, suspect TB",
  "recommended_service": "Infectious Disease",
  "priority": "urgent",
  "expected_arrival": "2025-01-16"
}
```

**Response (201 Created):**
```json
{
  "referral_id": "uuid",
  "patient_id": "uuid",
  "referral_number": "REF-20250115-001",
  "status": "pending",
  "referred_at": "2025-01-15T10:30:00Z",
  "referred_by": "Dr. Kwame Adjei"
}
```

---

### 7. Incoming Referrals

**GET** `/referrals/incoming`

**Permission:** doctor, hospital_admin

**Description:** Get referrals sent to this facility.

**Query Parameters:**
```
?status=pending&limit=20
```

**Response (200 OK):**
```json
{
  "count": 5,
  "results": [
    {
      "referral_id": "uuid",
      "patient_name": "Kwame Owusu",
      "referring_facility": "Ridge Regional Hospital",
      "referred_by": "Dr. Ama Kusi",
      "chief_complaint": "Acute appendicitis",
      "priority": "urgent",
      "status": "pending",
      "referred_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

### 8. Update Referral

**PUT** `/referrals/<uuid:pk>`

**Permission:** doctor (receiving facility)

**Description:** Accept, reject, or complete referral.

**Request Body:**
```json
{
  "status": "accepted",
  "acceptance_notes": "Patient arrived. Scheduled for surgery tomorrow."
}
```

**Response (200 OK):**
```json
{
  "referral_id": "uuid",
  "status": "accepted",
  "accepted_at": "2025-01-15T11:30:00Z"
}
```

---

### 9. Break-Glass Emergency Access

**POST** `/break-glass`

**Permission:** doctor, nurse, hospital_admin

**Description:** Access patient records in medical emergency (last 15 minutes only).

**Request Body:**
```json
{
  "patient_id": "uuid",
  "reason": "EMERGENCY_TREATMENT",
  "details": "Unconscious patient requiring immediate treatment. No consent available."
}
```

**Response (201 Created):**
```json
{
  "break_glass_id": "uuid",
  "patient_id": "uuid",
  "access_granted_at": "2025-01-15T14:30:00Z",
  "expires_at": "2025-01-15T14:45:00Z",
  "accessed_by": "Dr. Kwame Adjei",
  "reason": "EMERGENCY_TREATMENT",
  "status": "active",
  "audit_log_id": "uuid"
}
```

**Security Notes:**
- Access logged immediately with full context
- Automatically expires after 15 minutes
- Super admin notified for review
- Misuse can trigger escalation

---

### 10. Break-Glass List

**GET** `/break-glass/list`

**Permission:** doctor, hospital_admin

**Description:** View own break-glass accesses (last 30 days).

**Response (200 OK):**
```json
{
  "count": 3,
  "results": [
    {
      "break_glass_id": "uuid",
      "patient_name": "Kwame Owusu",
      "accessed_at": "2025-01-15T14:30:00Z",
      "reason": "EMERGENCY_TREATMENT",
      "accessed_by": "Dr. Kwame Adjei"
    }
  ]
}
```

---

### 11. Cross-Facility Records

**GET** `/cross-facility-records/<uuid:global_patient_id>`

**Permission:** doctor, hospital_admin (with consent)

**Description:** View patient records from other facilities (if consent granted).

**Response (200 OK):**
```json
{
  "patient_name": "Kwame Owusu",
  "facilities": [
    {
      "facility_name": "Ridge Regional Hospital",
      "scope": "FULL_RECORD",
      "records": [
        {
          "type": "diagnosis",
          "date": "2025-01-10",
          "data": {...}
        }
      ]
    }
  ]
}
```

---

---

## AI Intelligence

### 1. AI Status

**GET** `/ai/status`

**Permission:** IsAuthenticated

**Description:** Check if AI features are enabled for hospital.

**Response (200 OK):**
```json
{
  "ai_enabled": true,
  "hospital_id": "uuid",
  "hospital_name": "Korle-Bu Teaching Hospital",
  "features": [
    "patient_risk_prediction",
    "clinical_decision_support",
    "antibiotic_guidance",
    "no_show_risk",
    "similar_patient_finder"
  ],
  "last_model_updated": "2025-01-10T10:30:00Z"
}
```

---

### 2. Analyze Patient Comprehensive

**GET** `/ai/analyze-patient/<uuid:patient_id>`

**Permission:** doctor

**Description:** AI-powered comprehensive patient analysis with risk factors and recommendations.

**Query Parameters:**
```
?include=diagnoses,labs,medications,vitals
```

**Response (200 OK):**
```json
{
  "patient_id": "uuid",
  "patient_name": "Kwame Owusu",
  "analysis_timestamp": "2025-01-15T10:30:00Z",
  "overall_risk_score": 0.72,
  "risk_factors": [
    {
      "factor": "Hypertension (uncontrolled)",
      "weight": 0.35,
      "reasoning": "Recent BP readings 145-160 despite medication"
    },
    {
      "factor": "Age 60+",
      "weight": 0.25,
      "reasoning": "Age is significant cardiovascular risk"
    }
  ],
  "key_findings": [
    "Blood pressure control suboptimal",
    "Lipid panel pending",
    "ECG normal as of 2024-12"
  ],
  "recommendations": [
    {
      "recommendation": "Consider increasing lisinopril dose or adding amlodipine",
      "confidence": 0.85,
      "evidence": "Persistent BP > 140/90 despite current therapy"
    },
    {
      "recommendation": "Order lipid panel if not done in last 6 months",
      "confidence": 0.90,
      "evidence": "Age 60+, hypertensive, no recent lipid data"
    }
  ],
  "contraindications": [],
  "model_version": "v2.1"
}
```

---

### 3. Risk Prediction

**GET** `/ai/risk-prediction/<uuid:patient_id>`

**Permission:** doctor

**Description:** Predict patient risk (30-day readmission, mortality, complications).

**Query Parameters:**
```
?risk_type=readmission_30day
```

**Response (200 OK):**
```json
{
  "patient_id": "uuid",
  "risk_type": "readmission_30day",
  "risk_probability": 0.42,
  "risk_level": "moderate",
  "confidence_score": 0.78,
  "contributing_factors": [
    {"factor": "Age > 60", "contribution": 0.25},
    {"factor": "Chronic condition count (3)", "contribution": 0.35},
    {"factor": "Recent ED visits (2 in 30 days)", "contribution": 0.40}
  ],
  "mitigation_strategies": [
    "Ensure outpatient follow-up scheduled within 7 days",
    "Provide discharge medication reconciliation",
    "Arrange home health if high risk"
  ]
}
```

---

### 4. Clinical Decision Support

**GET** `/ai/clinical-decision-support/<uuid:patient_id>`

**Permission:** doctor

**Description:** AI-powered diagnostic and therapeutic recommendations.

**Response (200 OK):**
```json
{
  "patient_id": "uuid",
  "findings": {
    "chief_complaint": "Persistent fever for 3 weeks",
    "vitals": {"temperature": 38.5, "heart_rate": 105},
    "labs": {"wbc": 12.5, "crp": 85}
  },
  "differential_diagnoses": [
    {
      "diagnosis": "Tuberculosis",
      "probability": 0.65,
      "supporting_evidence": ["Chronic fever", "Weight loss", "No response to standard antibiotics"],
      "next_steps": ["Chest X-ray", "TB-LAMP test", "Consider TB specialist consultation"]
    },
    {
      "diagnosis": "Endocarditis",
      "probability": 0.25,
      "supporting_evidence": ["Fever", "Elevated inflammatory markers"],
      "next_steps": ["Echocardiogram", "Blood cultures", "ECG"]
    }
  ],
  "recommended_investigations": [
    "Chest X-ray",
    "TB-LAMP/GeneXpert",
    "Echocardiogram",
    "Blood cultures",
    "HIV test"
  ]
}
```

---

### 5. Antibiotic Guidance

**GET** `/ai/antibiotic-guidance`

**Permission:** doctor

**Description:** AI-powered antibiotic stewardship recommendations.

**Query Parameters:**
```
?infection_type=UTI&patient_id=uuid&severity=moderate
```

**Response (200 OK):**
```json
{
  "infection_type": "Urinary Tract Infection",
  "severity": "moderate",
  "patient_allergies": ["Penicillin"],
  "recommended_antibiotics": [
    {
      "drug": "Ciprofloxacin",
      "dose": "500mg",
      "frequency": "Twice daily",
      "duration": "7 days",
      "indication": "First-line for uncomplicated UTI",
      "evidence_strength": "strong"
    },
    {
      "drug": "Ceftriaxone",
      "dose": "1g",
      "frequency": "Once daily",
      "duration": "3 days",
      "indication": "Alternative if fluoroquinolone resistance concern",
      "evidence_strength": "moderate",
      "cross_reactivity_risk": "low"
    }
  ],
  "avoid": ["Amoxicillin (patient allergic)", "Trimethoprim-SMX (high resistance)"],
  "follow_up": "Culture results in 48-72 hours - adjust if needed"
}
```

---

### 6. No-Show Risk Prediction

**GET** `/ai/no-show-risk`

**Permission:** receptionist, hospital_admin

**Description:** Predict appointment no-show likelihood.

**Query Parameters:**
```
?appointment_id=uuid
```

**Response (200 OK):**
```json
{
  "appointment_id": "uuid",
  "patient_name": "Kwame Owusu",
  "no_show_probability": 0.38,
  "risk_level": "moderate",
  "risk_factors": [
    {"factor": "Previous no-shows: 2 of last 5 appointments", "weight": 0.50},
    {"factor": "Distance from facility: 25km", "weight": 0.30},
    {"factor": "Time of day: 8am (lower attendance)", "weight": 0.20}
  ],
  "recommended_actions": [
    "Send SMS reminder 24 hours before",
    "Consider rescheduling to afternoon slot",
    "Arrange patient transport if possible"
  ]
}
```

---

### 7. Find Similar Patients

**GET** `/ai/find-similar-patients/<uuid:patient_id>`

**Permission:** doctor

**Description:** Find patients with similar characteristics (demographics, diagnoses, risk profile).

**Query Parameters:**
```
?limit=5
```

**Response (200 OK):**
```json
{
  "reference_patient_id": "uuid",
  "similar_patients": [
    {
      "patient_id": "uuid",
      "similarity_score": 0.92,
      "common_attributes": [
        "Age 58-62",
        "Hypertension + Diabetes",
        "Similar BMI",
        "Previous MI"
      ],
      "outcomes": {
        "readmission_rate": "22%",
        "average_los_days": 4.5
      }
    }
  ]
}
```

---

### 8. Referral Recommendation

**GET** `/ai/referral-recommendation/<uuid:patient_id>`

**Permission:** doctor

**Description:** AI-powered hospital referral recommendation.

**Response (200 OK):**
```json
{
  "patient_id": "uuid",
  "current_facility": "Korle-Bu Teaching Hospital",
  "recommended_facilities": [
    {
      "facility_name": "Ridge Regional Hospital",
      "specialty": "Cardiothoracic Surgery",
      "reason": "Patient requires CABG - Ridge has best outcomes for this procedure",
      "confidence": 0.88,
      "estimated_travel_time": "35 minutes",
      "acceptance_likelihood": "95%"
    }
  ]
}
```

---

### 9. Async Analysis

**POST** `/ai/async-analysis/<uuid:patient_id>`

**Permission:** doctor

**Description:** Start long-running AI analysis job (returns job ID).

**Request Body:**
```json
{
  "analysis_type": "comprehensive",
  "include_cross_facility": true
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "patient_id": "uuid",
  "analysis_type": "comprehensive",
  "created_at": "2025-01-15T10:30:00Z",
  "estimated_wait_seconds": 15
}
```

---

### 10. Async Analysis Status

**GET** `/ai/async-analysis/status/<uuid:job_id>`

**Permission:** doctor

**Description:** Check status of async AI analysis job.

**Response (200 OK):**
```json
{
  "job_id": "uuid",
  "status": "in_progress",
  "progress_percent": 65,
  "started_at": "2025-01-15T10:30:00Z",
  "estimated_completion": "2025-01-15T10:45:00Z"
}
```

Or (when complete):

```json
{
  "job_id": "uuid",
  "status": "completed",
  "result": {...},
  "completed_at": "2025-01-15T10:42:00Z"
}
```

---

---

## Admin & Governance

### 1. List Users

**GET** `/admin/users`

**Permission:** hospital_admin, super_admin

**Description:** Get all staff users in hospital (or all if super_admin).

**Query Parameters:**
```
?role=doctor&status=active&search=kwame&limit=20
```

**Response (200 OK):**
```json
{
  "count": 45,
  "results": [
    {
      "user_id": "uuid",
      "email": "doctor@medsync.gh",
      "full_name": "Dr. Kwame Adjei",
      "role": "doctor",
      "hospital_id": "uuid",
      "hospital_name": "Korle-Bu Teaching Hospital",
      "ward_id": "uuid",
      "account_status": "active",
      "mfa_enabled": true,
      "last_login": "2025-01-15T10:30:00Z",
      "created_at": "2024-06-01T08:00:00Z"
    }
  ]
}
```

---

### 2. Invite User

**POST** `/admin/users/invite`

**Permission:** hospital_admin, super_admin

**Description:** Send invitation link to new staff member.

**Request Body:**
```json
{
  "email": "new.doctor@medsync.gh",
  "full_name": "Dr. Ama Kusi",
  "role": "doctor",
  "hospital_id": "uuid",
  "ward_id": "uuid",
  "send_email": true
}
```

**Response (201 Created):**
```json
{
  "user_id": "uuid",
  "email": "new.doctor@medsync.gh",
  "invitation_token": "inv_...",
  "invitation_expires": "2025-01-22T10:30:00Z",
  "status": "pending_activation"
}
```

---

### 3. Bulk Import Users

**POST** `/admin/users/bulk-import`

**Permission:** hospital_admin, super_admin

**Description:** Import multiple users from CSV.

**Request Body (multipart/form-data):**
```
file: users.csv
```

**CSV Format:**
```
email,full_name,role,ward_id
doctor1@medsync.gh,Dr. Kwame,doctor,ward-uuid
nurse1@medsync.gh,Nurse Akosua,nurse,ward-uuid
```

**Response (200 OK):**
```json
{
  "total": 2,
  "created": 2,
  "failed": 0,
  "results": [
    {
      "email": "doctor1@medsync.gh",
      "status": "success",
      "user_id": "uuid"
    }
  ]
}
```

---

### 4. Update User

**PUT** `/admin/users/<uuid:pk>`

**Permission:** hospital_admin (own hospital), super_admin

**Description:** Update user profile (role, ward, status).

**Request Body:**
```json
{
  "full_name": "Dr. Kwame Adjei",
  "role": "senior_doctor",
  "ward_id": "uuid",
  "account_status": "active"
}
```

**Response (200 OK):**
```json
{
  "user_id": "uuid",
  "full_name": "Dr. Kwame Adjei",
  "role": "senior_doctor",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

### 5. Audit Logs

**GET** `/admin/audit-logs`

**Permission:** hospital_admin, super_admin

**Description:** View audit trail of all actions in hospital.

**Query Parameters:**
```
?action=CREATE&resource_type=patient&start_date=2025-01-01&end_date=2025-01-15&limit=100
```

**Response (200 OK):**
```json
{
  "count": 523,
  "results": [
    {
      "audit_id": "uuid",
      "timestamp": "2025-01-15T10:30:00Z",
      "actor": "Dr. Kwame Adjei",
      "action": "CREATE",
      "resource_type": "patient",
      "resource_id": "GHA-2025-001",
      "hospital": "Korle-Bu Teaching Hospital",
      "ip_address": "192.168.1.100",
      "status": "success"
    }
  ]
}
```

---

### 6. Security Alerts

**GET** `/superadmin/security/alerts`

**Permission:** super_admin, hospital_admin

**Description:** Get security alerts (failed logins, suspicious activity, break-glass use).

**Response (200 OK):**
```json
{
  "critical": [
    {
      "alert_id": "uuid",
      "type": "failed_logins_threshold",
      "severity": "high",
      "description": "User doctor@medsync.gh had 5 failed login attempts in 10 minutes",
      "timestamp": "2025-01-15T10:30:00Z",
      "action_taken": "Account locked for 15 minutes"
    }
  ],
  "warnings": [...]
}
```

---

### 7. System Health

**GET** `/superadmin/system-health`

**Permission:** super_admin

**Description:** System status dashboard (database, AI, queue, cache).

**Response (200 OK):**
```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "overall_status": "healthy",
  "components": {
    "database": {
      "status": "ok",
      "connection_pool": "12/20",
      "query_latency_ms": 45
    },
    "ai_model": {
      "status": "ok",
      "requests_queue": 3,
      "avg_response_time_ms": 1200
    },
    "cache": {
      "status": "ok",
      "hit_rate": "92%",
      "memory_usage_mb": 450
    },
    "background_tasks": {
      "status": "ok",
      "pending_tasks": 12,
      "failed_tasks_24h": 0
    }
  },
  "alerts": []
}
```

---

---

## Batch Operations

### 1. Batch Import

**POST** `/batch-import`

**Permission:** hospital_admin, super_admin

**Description:** Create batch import job for patients/records/appointments.

**Request Body (multipart/form-data):**
```
file: patients.csv
import_type: patients
```

**Response (201 Created):**
```json
{
  "job_id": "uuid",
  "import_type": "patients",
  "status": "queued",
  "total_records": 150,
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 2. Batch Import Status

**GET** `/batch-import/<uuid:job_id>`

**Permission:** hospital_admin, super_admin

**Description:** Check batch import progress.

**Response (200 OK):**
```json
{
  "job_id": "uuid",
  "status": "in_progress",
  "progress": {
    "total": 150,
    "completed": 95,
    "failed": 3,
    "percent": 63
  },
  "started_at": "2025-01-15T10:30:00Z",
  "estimated_completion": "2025-01-15T11:00:00Z"
}
```

---

### 3. Batch Import Items

**GET** `/batch-import/<uuid:job_id>/items`

**Permission:** hospital_admin, super_admin

**Description:** Get detailed results of each item in batch (failures + successes).

**Query Parameters:**
```
?status=failed&limit=20
```

**Response (200 OK):**
```json
{
  "count": 3,
  "results": [
    {
      "item_id": "uuid",
      "row_number": 42,
      "status": "failed",
      "error": "Duplicate patient: Patient with name 'Kwame Owusu' and DOB '1990-05-15' already exists",
      "data": {"full_name": "Kwame Owusu", "date_of_birth": "1990-05-15"}
    }
  ]
}
```

---

### 4. Batch Import Export

**GET** `/batch-import/<uuid:job_id>/export`

**Permission:** hospital_admin, super_admin

**Description:** Download detailed batch import report (CSV/JSON).

**Query Parameters:**
```
?format=csv
```

**Response:** CSV/JSON file download

---

### 5. Bulk Invitations

**POST** `/bulk-invitations`

**Permission:** hospital_admin, super_admin

**Description:** Create bulk invitation campaign (e.g., invite 50 staff at once).

**Request Body:**
```json
{
  "campaign_name": "Q1 2025 Onboarding",
  "invites": [
    {"email": "user1@medsync.gh", "full_name": "User One", "role": "doctor"},
    {"email": "user2@medsync.gh", "full_name": "User Two", "role": "nurse"}
  ],
  "send_immediately": false,
  "scheduled_send": "2025-01-20T08:00:00Z"
}
```

**Response (201 Created):**
```json
{
  "campaign_id": "uuid",
  "campaign_name": "Q1 2025 Onboarding",
  "total_invites": 2,
  "status": "scheduled",
  "scheduled_send": "2025-01-20T08:00:00Z"
}
```

---

---

## Reporting & Analytics

### 1. Export Patients CSV

**GET** `/reports/patients/export`

**Permission:** hospital_admin, super_admin

**Description:** Export patient list as CSV.

**Query Parameters:**
```
?status=active&start_date=2025-01-01&end_date=2025-01-15
```

**Response:** CSV file download

---

### 2. Export Audit CSV

**GET** `/reports/audit/export`

**Permission:** hospital_admin, super_admin

**Description:** Export audit log as CSV for compliance.

**Query Parameters:**
```
?action=CREATE,UPDATE&resource_type=patient&start_date=2025-01-01
```

**Response:** CSV file download

---

### 3. Dashboard Metrics

**GET** `/dashboard/metrics`

**Permission:** IsAuthenticated

**Description:** Role-specific dashboard metrics (appointments, patients, alerts).

**Response (200 OK) - Doctor:**
```json
{
  "today": {
    "appointments": 8,
    "patients_seen": 5,
    "new_admissions": 1,
    "pending_labs": 3,
    "critical_alerts": 1
  },
  "this_week": {
    "appointments": 35,
    "new_patients": 12
  },
  "this_month": {
    "appointments": 145,
    "new_patients": 45
  }
}
```

**Response (200 OK) - Hospital Admin:**
```json
{
  "occupancy": {
    "total_beds": 100,
    "occupied": 75,
    "occupancy_rate": "75%"
  },
  "staff": {
    "doctors": 25,
    "nurses": 60,
    "on_duty_today": 82
  },
  "patients": {
    "total_active": 75,
    "new_this_month": 180,
    "discharged_this_month": 165
  }
}
```

---

---

## FHIR & HL7

### 1. FHIR Patient List

**GET** `/fhir/Patient`

**Permission:** IsAuthenticated (read-only)

**Description:** Get patients in FHIR Patient resource format.

**Response (200 OK):**
```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 2,
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "uuid",
        "identifier": [
          {"system": "http://medsync.gh/ghana-health-id", "value": "GHA-2025-00001"}
        ],
        "name": [{"given": ["Kwame"], "family": "Owusu"}],
        "gender": "male",
        "birthDate": "1990-05-15",
        "address": [{"text": "Accra, Ghana"}]
      }
    }
  ]
}
```

---

### 2. FHIR Encounter

**GET** `/fhir/Encounter/<uuid:pk>`

**Permission:** IsAuthenticated (read-only)

**Description:** Get encounter in FHIR Encounter resource format.

**Response (200 OK):**
```json
{
  "resourceType": "Encounter",
  "id": "uuid",
  "status": "finished",
  "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
  "subject": {"reference": "Patient/uuid"},
  "type": [{"coding": [{"code": "follow-up"}]}],
  "period": {"start": "2025-01-15T10:00:00Z", "end": "2025-01-15T11:30:00Z"},
  "reasonCode": [{"text": "Hypertension follow-up"}]
}
```

---

### 3. FHIR Condition (Diagnosis)

**GET** `/fhir/Condition/<uuid:pk>`

**Permission:** IsAuthenticated (read-only)

**Description:** Get diagnosis in FHIR Condition resource format.

**Response (200 OK):**
```json
{
  "resourceType": "Condition",
  "id": "uuid",
  "clinicalStatus": {"coding": [{"code": "active"}]},
  "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "I10", "display": "Essential hypertension"}]},
  "subject": {"reference": "Patient/uuid"},
  "onsetDateTime": "2024-12-01"
}
```

---

### 4. FHIR MedicationRequest

**GET** `/fhir/MedicationRequest/<uuid:pk>`

**Permission:** IsAuthenticated (read-only)

**Description:** Get prescription in FHIR MedicationRequest format.

---

### 5. FHIR Observation (Vitals)

**GET** `/fhir/Observation/<uuid:pk>`

**Permission:** IsAuthenticated (read-only)

**Description:** Get vital signs in FHIR Observation format.

---

### 6. HL7 ADT List

**GET** `/hl7/adt`

**Permission:** IsAuthenticated (read-only)

**Description:** Get ADT (Admit-Discharge-Transfer) messages in HL7 v2 format.

---

### 7. FHIR Push (Export)

**POST** `/interop/fhir-push`

**Permission:** super_admin

**Description:** Push FHIR bundle to external system (HIE network node).

**Request Body:**
```json
{
  "destination_url": "https://hie-node.example.com/fhir",
  "resource_types": ["Patient", "Encounter", "Condition"],
  "filters": {"status": "active"}
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "destination": "https://hie-node.example.com/fhir"
}
```

---

---

## Error Response Examples

### Validation Error
```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "details": {
    "full_name": ["This field is required"],
    "date_of_birth": ["Invalid date format. Use YYYY-MM-DD"]
  }
}
```

### Authentication Error
```json
{
  "error": "Authentication failed",
  "code": "UNAUTHORIZED",
  "message": "Invalid or expired token"
}
```

### Permission Error
```json
{
  "error": "Permission denied",
  "code": "FORBIDDEN",
  "message": "User role 'nurse' cannot access this endpoint"
}
```

### Not Found
```json
{
  "error": "Resource not found",
  "code": "NOT_FOUND",
  "message": "Patient with ID 'uuid' not found"
}
```

### Rate Limit
```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after_seconds": 60
}
```

---

## Rate Limiting

All API endpoints are rate-limited to prevent abuse:

- **Login:** 5 attempts per minute per IP
- **MFA:** 10 attempts per minute per user
- **General API:** 100 requests per minute per user (adjustable by role)
- **Password Reset:** 3 attempts per day per email
- **Bulk Operations:** 10 per day per hospital

---

## API Versioning

Current version: `v1`

Future versions will be released as `/api/v2`, `/api/v3`, etc., with v1 supported for 12 months post-release.

---

**For support or questions:** contact api-support@medsync.gh
