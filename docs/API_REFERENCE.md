# MedSync EMR API Reference

**Version:** 1.0  
**Base URL:** `https://api.medsync.app/api/v1` (production) or `http://localhost:8000/api/v1` (development)  
**Authentication:** JWT + TOTP MFA  
**Rate Limit:** See [Rate Limiting](#rate-limiting) section

---

## Error Codes & Status Legend

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|--------------|
| **200** | OK | Request succeeded |
| **201** | Created | Resource created successfully |
| **400** | Bad Request | Invalid input, missing required field, validation error |
| **401** | Unauthorized | Missing/invalid JWT token, MFA required, session expired |
| **403** | Forbidden | Insufficient permissions, hospital scoping restriction, role not authorized |
| **404** | Not Found | Resource does not exist, patient not found in your facility |
| **429** | Too Many Requests | Rate limit exceeded (login, MFA, password reset) |
| **503** | Service Unavailable | Database unreachable, email service down, dependencies offline |

### Common Error Response Format

```json
{
  "message": "Descriptive error message",
  "code": "ERROR_CODE",
  "details": {
    "field": ["Error for this field"]
  }
}
```

### Authentication-Specific Error Codes

| Code | Meaning | Resolution |
|------|---------|-----------|
| `INVALID_CREDENTIALS` | Email or password incorrect | Verify credentials; check for caps lock |
| `MFA_REQUIRED` | MFA code needed | Submit MFA code to `/auth/mfa-verify` |
| `MFA_SESSION_EXPIRED` | MFA token expired | Re-login and submit MFA again |
| `ACCOUNT_LOCKED` | Too many failed attempts | Wait 1 hour or contact hospital admin |
| `TOKEN_EXPIRED` | Access token expired | Use refresh token to get new access token |
| `INVALID_REFRESH_TOKEN` | Refresh token invalid/blacklisted | Re-login |
| `PERMISSION_DENIED` | User role not authorized for endpoint | Contact hospital admin to update role |

---

## Rate Limiting

### Global Limits

| Endpoint Category | Authenticated | Anonymous |
|------------------|--------------|-----------|
| **Login** | 5 attempts/15 min (per IP) | 5 attempts/15 min (per IP) |
| **MFA Verify** | 3 attempts/5 min (per IP) | 3 attempts/5 min (per IP) |
| **Password Reset** | 3 requests/hour (per IP) | 3 requests/hour (per IP) |
| **General API** | 1000 requests/hour | 60 requests/hour |

### Rate Limit Response Headers

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640000000
Retry-After: 60
```

When rate limited, the API returns **429 Too Many Requests** with:

```json
{
  "message": "Rate limit exceeded. Try again after 60 seconds.",
  "retry_after": 60
}
```

---

## Authentication

### POST `/auth/login`

Log in a user with email and password.

**Authentication Required:** No (Public)  
**Rate Limit:** 5 attempts/15 min  

**Request:**
```json
{
  "email": "doctor@medsync.gh",
  "password": "SecurePass123!@#"
}
```

**Response (200 - MFA Required):**
```json
{
  "mfa_required": true,
  "mfa_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "mfa_channel": "email"
}
```

**Response (401 - Invalid Credentials):**
```json
{
  "message": "Invalid email or password"
}
```

**Response (429 - Rate Limited):**
```json
{
  "message": "Account locked due to too many failed login attempts. Try again later."
}
```

---

### POST `/auth/mfa-verify`

Verify TOTP or backup code for MFA.

**Authentication Required:** No (Public)  
**Rate Limit:** 3 attempts/5 min per IP; 10 failures/hour locks account  

**Request (TOTP):**
```json
{
  "mfa_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "code": "123456"
}
```

**Request (Backup Code):**
```json
{
  "mfa_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "backup_code": "a1b2c3d4"
}
```

**Response (200 - Success):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzIiwicm9sZSI6ImRvY3RvciJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDAyMDAwMDB9...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "doctor@medsync.gh",
    "full_name": "Dr. John Doe",
    "role": "doctor",
    "hospital_id": "550e8400-e29b-41d4-a716-446655440001",
    "hospital_name": "Korle Bu Teaching Hospital"
  }
}
```

**Response (401 - Invalid Code):**
```json
{
  "message": "Invalid code. Try again."
}
```

**Response (429 - Account Locked):**
```json
{
  "message": "Account locked due to too many failed MFA attempts. Try again after 1 hour.",
  "locked_until": "2024-12-20T15:30:00Z"
}
```

---

### POST `/auth/refresh`

Get a new access token using a refresh token.

**Authentication Required:** No (Public)  

**Request:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 - Success):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (401 - Invalid Token):**
```json
{
  "message": "Token is blacklisted or invalid"
}
```

---

### POST `/auth/logout`

Log out the current user and blacklist tokens.

**Authentication Required:** Yes (JWT)  

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 - Success):**
```json
{
  "message": "Logout successful"
}
```

---

### GET `/auth/me`

Get the current authenticated user's profile.

**Authentication Required:** Yes (JWT)  

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "doctor@medsync.gh",
  "full_name": "Dr. John Doe",
  "role": "doctor",
  "hospital_id": "550e8400-e29b-41d4-a716-446655440001",
  "hospital_name": "Korle Bu Teaching Hospital",
  "ward_id": null,
  "date_joined": "2024-01-15T10:00:00Z",
  "last_login": "2024-12-20T08:30:00Z"
}
```

---

### POST `/auth/forgot-password`

Request a password reset email.

**Authentication Required:** No (Public)  
**Rate Limit:** 3 requests/hour per IP  

**Request:**
```json
{
  "email": "doctor@medsync.gh"
}
```

**Response (200 - Email Sent):**
```json
{
  "message": "Password reset link sent to your email. Link expires in 24 hours."
}
```

**Response (404 - Not Found):**
```json
{
  "message": "Email not found"
}
```

---

### POST `/auth/reset-password`

Reset password using the reset token.

**Authentication Required:** No (Public)  

**Request:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "new_password": "NewSecurePass123!@#"
}
```

**Response (200 - Success):**
```json
{
  "message": "Password updated successfully. Please login with your new password."
}
```

**Response (400 - Validation Error):**
```json
{
  "message": "Password does not meet requirements",
  "details": {
    "password": [
      "Must be at least 12 characters long",
      "Must contain uppercase, lowercase, digit, and symbol"
    ]
  }
}
```

---

## Patients

### GET `/patients/search`

Search for patients in your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, lab_technician, receptionist, hospital_admin, super_admin  

**Query Parameters:**
- `q`: Search by name, Ghana Health ID, phone number (partial match)
- `ghana_health_id`: Exact search by Ghana Health ID
- `dob`: Filter by date of birth (YYYY-MM-DD)

**Request:**
```
GET /api/v1/patients/search?q=John&limit=10
```

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "full_name": "John Kwame Mensah",
      "ghana_health_id": "GHA-123-456-789",
      "date_of_birth": "1990-05-15",
      "phone": "+233501234567",
      "nhis_number": "NHIS-001-2024",
      "gender": "M",
      "hospital_id": "550e8400-e29b-41d4-a716-446655440001",
      "registered_at": "2024-01-15T10:00:00Z"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

**Response (403 - Permission Denied):**
```json
{
  "message": "Permission denied"
}
```

---

### POST `/patients`

Register a new patient in your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** receptionist, doctor, nurse, hospital_admin, super_admin  

**Request:**
```json
{
  "full_name": "John Kwame Mensah",
  "ghana_health_id": "GHA-123-456-789",
  "date_of_birth": "1990-05-15",
  "phone": "+233501234567",
  "gender": "M",
  "nhis_number": "NHIS-001-2024",
  "address": "123 Accra Street, Accra, Ghana",
  "emergency_contact": "+233509876543"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "full_name": "John Kwame Mensah",
  "ghana_health_id": "GHA-123-456-789",
  "date_of_birth": "1990-05-15",
  "phone": "+233501234567",
  "gender": "M",
  "nhis_number": "NHIS-001-2024",
  "address": "123 Accra Street, Accra, Ghana",
  "emergency_contact": "+233509876543",
  "registered_at": "2024-12-20T10:00:00Z",
  "hospital_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Response (400 - Duplicate Patient):**
```json
{
  "message": "Patient with this Ghana Health ID already exists"
}
```

---

### GET `/patients/<uuid:pk>`

Get detailed patient information.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, lab_technician, hospital_admin, super_admin  

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "full_name": "John Kwame Mensah",
  "ghana_health_id": "GHA-123-456-789",
  "date_of_birth": "1990-05-15",
  "age": 34,
  "phone": "+233501234567",
  "gender": "M",
  "nhis_number": "NHIS-001-2024",
  "address": "123 Accra Street, Accra, Ghana",
  "emergency_contact": "+233509876543",
  "registered_at": "2024-01-15T10:00:00Z",
  "hospital_id": "550e8400-e29b-41d4-a716-446655440001",
  "active_admission": {
    "id": "550e8400-e29b-41d4-a716-446655440100",
    "ward_id": "550e8400-e29b-41d4-a716-446655440101",
    "ward_name": "Medical Ward",
    "bed_name": "M-01",
    "admitted_at": "2024-12-18T08:00:00Z",
    "discharged_at": null
  }
}
```

**Response (404 - Not Found):**
```json
{
  "message": "Patient not found"
}
```

**Response (403 - Cross-Facility Without Consent):**
```json
{
  "message": "Permission denied. Cross-facility access requires consent."
}
```

---

### GET `/patients/<uuid:pk>/records`

Get all medical records for a patient.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, lab_technician, hospital_admin, super_admin  

**Query Parameters:**
- `type`: Filter by record type (diagnosis, prescription, vital, lab_result, nursing_note)
- `limit`: Records per page (default: 50, max: 100)
- `offset`: Pagination offset

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440200",
      "type": "diagnosis",
      "created_by": "Dr. John Doe",
      "created_at": "2024-12-20T10:00:00Z",
      "content": {
        "icd10_code": "I10",
        "icd10_description": "Essential hypertension",
        "severity": "moderate"
      }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440201",
      "type": "prescription",
      "created_by": "Dr. John Doe",
      "created_at": "2024-12-20T10:05:00Z",
      "content": {
        "drug_name": "Lisinopril",
        "dosage": "10mg",
        "frequency": "Once daily",
        "duration": "30 days"
      }
    }
  ],
  "total_count": 2,
  "limit": 50,
  "offset": 0
}
```

---

## Records (Clinical)

### POST `/records/diagnosis`

Create a new diagnosis record.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "encounter_id": "550e8400-e29b-41d4-a716-446655440300",
  "icd10_code": "I10",
  "icd10_description": "Essential hypertension",
  "severity": "moderate",
  "status": "active",
  "notes": "Patient presenting with elevated BP"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440200",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "encounter_id": "550e8400-e29b-41d4-a716-446655440300",
  "icd10_code": "I10",
  "icd10_description": "Essential hypertension",
  "severity": "moderate",
  "status": "active",
  "notes": "Patient presenting with elevated BP",
  "created_by": "Dr. John Doe",
  "created_at": "2024-12-20T10:00:00Z",
  "amended_at": null
}
```

**Response (400 - Invalid Patient/Encounter):**
```json
{
  "message": "Patient or encounter not found in your facility"
}
```

**Response (403 - Permission Denied):**
```json
{
  "message": "Permission denied. Only doctors can create diagnoses."
}
```

---

### POST `/records/prescription`

Create a new prescription.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "encounter_id": "550e8400-e29b-41d4-a716-446655440300",
  "drug_name": "Lisinopril",
  "dosage": "10mg",
  "frequency": "Once daily",
  "duration": "30 days",
  "route": "oral",
  "special_instructions": "Take with food",
  "quantity": 30,
  "refills_remaining": 2
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440201",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "drug_name": "Lisinopril",
  "dosage": "10mg",
  "frequency": "Once daily",
  "route": "oral",
  "status": "pending",
  "dispensed_by": null,
  "dispensed_at": null,
  "created_by": "Dr. John Doe",
  "created_at": "2024-12-20T10:05:00Z"
}
```

---

### POST `/records/vitals`

Create vital signs record.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** nurse, doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "encounter_id": "550e8400-e29b-41d4-a716-446655440300",
  "temperature": 37.2,
  "heart_rate": 72,
  "blood_pressure_systolic": 120,
  "blood_pressure_diastolic": 80,
  "respiratory_rate": 16,
  "oxygen_saturation": 98.5,
  "blood_glucose": 110,
  "measured_at": "2024-12-20T10:00:00Z"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440400",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "temperature": 37.2,
  "heart_rate": 72,
  "blood_pressure_systolic": 120,
  "blood_pressure_diastolic": 80,
  "respiratory_rate": 16,
  "oxygen_saturation": 98.5,
  "blood_glucose": 110,
  "measured_at": "2024-12-20T10:00:00Z",
  "created_by": "Nurse Jane Adu",
  "created_at": "2024-12-20T10:00:00Z",
  "qsofa_score": 0,
  "news2_score": 2
}
```

---

### POST `/records/lab-order`

Create a laboratory order.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "encounter_id": "550e8400-e29b-41d4-a716-446655440300",
  "lab_test_type_id": "550e8400-e29b-41d4-a716-446655440501",
  "urgency": "routine",
  "clinical_indication": "Routine check-up",
  "ordered_at": "2024-12-20T10:00:00Z"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440500",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "lab_test_type": {
    "id": "550e8400-e29b-41d4-a716-446655440501",
    "name": "Full Blood Count"
  },
  "urgency": "routine",
  "status": "pending",
  "clinical_indication": "Routine check-up",
  "ordered_by": "Dr. John Doe",
  "ordered_at": "2024-12-20T10:00:00Z",
  "result": null
}
```

---

### POST `/records/lab-order/<uuid:order_id>/result`

Submit lab result for an order.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** lab_technician, hospital_admin, super_admin  

**Request:**
```json
{
  "result_value": "12.5",
  "unit": "g/dL",
  "reference_range": "13.5-17.5",
  "status": "normal",
  "notes": "Within normal range",
  "tested_at": "2024-12-20T11:00:00Z"
}
```

**Response (200 - Updated):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440500",
  "status": "completed",
  "result": {
    "value": "12.5",
    "unit": "g/dL",
    "reference_range": "13.5-17.5",
    "status": "normal",
    "notes": "Within normal range",
    "tested_at": "2024-12-20T11:00:00Z"
  },
  "completed_by": "Lab Tech Ahmed Hassan",
  "completed_at": "2024-12-20T11:00:00Z"
}
```

---

## Admissions

### POST `/admissions/create`

Create a patient admission to a ward.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, hospital_admin, super_admin  

**Request:**
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "ward_id": "550e8400-e29b-41d4-a716-446655440101",
  "bed_id": "550e8400-e29b-41d4-a716-446655440102",
  "reason": "Hypertension management",
  "admitted_at": "2024-12-20T08:00:00Z"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440100",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "ward_id": "550e8400-e29b-41d4-a716-446655440101",
  "ward_name": "Medical Ward",
  "bed_id": "550e8400-e29b-41d4-a716-446655440102",
  "bed_name": "M-01",
  "reason": "Hypertension management",
  "admitted_at": "2024-12-20T08:00:00Z",
  "discharged_at": null,
  "length_of_stay_hours": null
}
```

**Response (400 - Bed Not Available):**
```json
{
  "message": "Bed is not available or already occupied"
}
```

---

### POST `/admissions/<uuid:admission_id>/discharge`

Discharge a patient from hospital.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, hospital_admin, super_admin  

**Request:**
```json
{
  "discharge_summary": "Patient stable, condition improved",
  "follow_up_instructions": "Follow up in 1 week",
  "discharged_at": "2024-12-20T14:00:00Z"
}
```

**Response (200 - Updated):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440100",
  "patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "discharged_at": "2024-12-20T14:00:00Z",
  "discharge_summary": "Patient stable, condition improved",
  "follow_up_instructions": "Follow up in 1 week",
  "length_of_stay_hours": 30
}
```

---

## Encounters

### GET `/patients/<uuid:pk>/encounters`

Get all encounters for a patient.

**Authentication Required:** Yes (JWT)  

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440300",
      "patient_id": "550e8400-e29b-41d4-a716-446655440002",
      "encounter_type": "inpatient",
      "chief_complaint": "Elevated blood pressure",
      "assessment": "Essential hypertension, uncontrolled",
      "plan": "Increase antihypertensive medication",
      "started_at": "2024-12-20T09:00:00Z",
      "closed_at": null,
      "provider_id": "550e8400-e29b-41d4-a716-446655440600",
      "provider_name": "Dr. John Doe"
    }
  ],
  "total_count": 1
}
```

---

### POST `/patients/<uuid:pk>/encounters/<uuid:encounter_id>/close`

Close an encounter.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "outcome": "recovered",
  "notes": "Patient improved, stable for discharge"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440300",
  "closed_at": "2024-12-20T14:00:00Z",
  "outcome": "recovered"
}
```

---

## Referrals & Interoperability

### POST `/referrals`

Create a referral to another facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "to_facility_id": "550e8400-e29b-41d4-a716-446655440700",
  "reason": "Specialized cardiology consultation",
  "urgency": "routine",
  "clinical_summary": "Patient with persistent hypertension, needs cardiology review"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440800",
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "from_facility_id": "550e8400-e29b-41d4-a716-446655440001",
  "to_facility_id": "550e8400-e29b-41d4-a716-446655440700",
  "reason": "Specialized cardiology consultation",
  "urgency": "routine",
  "status": "pending",
  "created_by": "Dr. John Doe",
  "created_at": "2024-12-20T10:00:00Z"
}
```

---

### GET `/referrals/incoming`

Get incoming referrals for your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440800",
      "from_facility": "Korle Bu Teaching Hospital",
      "patient_name": "John Kwame Mensah",
      "reason": "Specialized cardiology consultation",
      "urgency": "routine",
      "status": "pending",
      "referred_at": "2024-12-20T10:00:00Z"
    }
  ],
  "total_count": 1
}
```

---

### PATCH `/referrals/<uuid:pk>`

Accept or reject a referral.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  

**Request:**
```json
{
  "status": "accepted",
  "notes": "Ready to receive patient for cardiology assessment"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440800",
  "status": "accepted",
  "notes": "Ready to receive patient for cardiology assessment"
}
```

---

### POST `/consents`

Grant another facility access to patient records.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** patient (via frontend), hospital_admin, super_admin  

**Request:**
```json
{
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "granted_to_facility_id": "550e8400-e29b-41d4-a716-446655440700",
  "scope": "FULL_RECORD",
  "expires_at": "2025-12-20T23:59:59Z"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440900",
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "granted_to_facility_id": "550e8400-e29b-41d4-a716-446655440700",
  "scope": "FULL_RECORD",
  "is_active": true,
  "expires_at": "2025-12-20T23:59:59Z",
  "created_at": "2024-12-20T10:00:00Z"
}
```

---

### GET `/consents/list`

List all consents for records your facility has access to.

**Authentication Required:** Yes (JWT)  

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440900",
      "patient_name": "John Kwame Mensah",
      "from_facility": "Korle Bu Teaching Hospital",
      "scope": "FULL_RECORD",
      "is_active": true,
      "expires_at": "2025-12-20T23:59:59Z",
      "created_at": "2024-12-20T10:00:00Z"
    }
  ],
  "total_count": 1
}
```

---

### DELETE `/consents/<uuid:pk>`

Revoke consent for a facility to access records.

**Authentication Required:** Yes (JWT)  

**Response (200):**
```json
{
  "message": "Consent revoked successfully"
}
```

---

### POST `/break-glass`

Use emergency break-glass access to view patient records (last 15 minutes only).

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, hospital_admin, super_admin  
**Audit Logging:** Full audit trail with emergency flag  

**Request:**
```json
{
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "reason": "Patient in critical condition, emergency surgery needed"
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440950",
  "global_patient_id": "550e8400-e29b-41d4-a716-446655440002",
  "reason": "Patient in critical condition, emergency surgery needed",
  "accessed_by": "Dr. John Doe",
  "accessed_at": "2024-12-20T10:00:00Z",
  "expires_at": "2024-12-20T10:15:00Z"
}
```

---

## Alerts

### GET `/alerts`

Get active clinical alerts for your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** doctor, nurse, hospital_admin, super_admin  

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655441000",
      "patient_id": "550e8400-e29b-41d4-a716-446655440002",
      "patient_name": "John Kwame Mensah",
      "alert_type": "high_blood_pressure",
      "severity": "high",
      "message": "Systolic BP 160 mmHg - Above 140 threshold",
      "created_at": "2024-12-20T10:00:00Z",
      "resolved_at": null
    }
  ],
  "total_count": 1
}
```

---

### POST `/alerts/<uuid:pk>/resolve`

Resolve an active alert.

**Authentication Required:** Yes (JWT)  

**Request:**
```json
{
  "resolution_notes": "Patient started on antihypertensive therapy"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655441000",
  "resolved_at": "2024-12-20T10:30:00Z",
  "resolution_notes": "Patient started on antihypertensive therapy"
}
```

---

## Lab Management

### GET `/lab/orders`

Get all lab orders for your lab.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** lab_technician, hospital_admin, super_admin  

**Query Parameters:**
- `status`: Filter by status (pending, completed, rejected)
- `ward_id`: Filter by requesting ward
- `limit`: Results per page

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440500",
      "patient_name": "John Kwame Mensah",
      "lab_test_type": "Full Blood Count",
      "urgency": "routine",
      "status": "pending",
      "ordered_by": "Dr. John Doe",
      "ordered_at": "2024-12-20T10:00:00Z"
    }
  ],
  "total_count": 1
}
```

---

## Admin/User Management

### GET `/admin/users`

List all users in your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** hospital_admin, super_admin  

**Query Parameters:**
- `role`: Filter by role (doctor, nurse, lab_technician, receptionist, hospital_admin)
- `status`: Filter by account status (active, inactive, pending)

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440600",
      "email": "doctor@medsync.gh",
      "full_name": "Dr. John Doe",
      "role": "doctor",
      "account_status": "active",
      "last_login": "2024-12-20T08:30:00Z"
    }
  ],
  "total_count": 1
}
```

---

### POST `/admin/users/invite`

Invite a new user to your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** hospital_admin, super_admin  

**Request:**
```json
{
  "email": "newdoctor@medsync.gh",
  "full_name": "Dr. Jane Smith",
  "role": "doctor",
  "ward_id": null
}
```

**Response (201 - Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440601",
  "email": "newdoctor@medsync.gh",
  "full_name": "Dr. Jane Smith",
  "role": "doctor",
  "account_status": "pending",
  "created_at": "2024-12-20T10:00:00Z"
}
```

---

### POST `/admin/users/<uuid:pk>/reset-mfa`

Reset MFA for a locked user.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** hospital_admin, super_admin  

**Request:**
```json
{}
```

**Response (200):**
```json
{
  "message": "MFA reset for user. User must set up MFA again on next login."
}
```

---

### GET `/admin/audit-logs`

Get audit logs for your facility.

**Authentication Required:** Yes (JWT)  
**Authorized Roles:** hospital_admin, super_admin  

**Query Parameters:**
- `user_id`: Filter by user
- `action`: Filter by action type (VIEW, CREATE, UPDATE, DELETE, EMERGENCY_ACCESS)
- `days`: Filter last N days (default: 30)

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655441100",
      "user": "Dr. John Doe",
      "action": "CREATE",
      "resource_type": "Diagnosis",
      "resource_id": "550e8400-e29b-41d4-a716-446655440200",
      "timestamp": "2024-12-20T10:00:00Z",
      "ip_address": "192.168.1.1",
      "details": {
        "patient_name": "John Kwame Mensah",
        "icd10_code": "I10"
      }
    }
  ],
  "total_count": 1000
}
```

---

## Health & System

### GET `/health`

Check API health status.

**Authentication Required:** No (Public)  

**Response (200 - Healthy):**
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "email": "configured",
  "timestamp": "2024-12-20T10:00:00Z"
}
```

**Response (503 - Unhealthy):**
```json
{
  "status": "unhealthy",
  "database": "unreachable",
  "cache": "unavailable",
  "email": "unconfigured",
  "error": "Database connection refused"
}
```

---

## FHIR Interoperability (Read-Only)

### GET `/fhir/Patient`

Get all patients in FHIR format (read-only).

**Authentication Required:** Yes (JWT)  

**Response (200):**
```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 1,
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": [{"text": "John Kwame Mensah"}],
        "birthDate": "1990-05-15",
        "gender": "male",
        "identifier": [{"value": "GHA-123-456-789"}]
      }
    }
  ]
}
```

---

## Summary Table of Key Endpoints

| Method | Endpoint | Role | Purpose |
|--------|----------|------|---------|
| POST | `/auth/login` | Public | Authenticate user |
| POST | `/auth/mfa-verify` | Public | Verify MFA code |
| POST | `/auth/refresh` | Public | Get new access token |
| POST | `/auth/logout` | Authenticated | Logout and revoke tokens |
| GET | `/patients/search` | Clinical | Search for patients |
| POST | `/patients` | Clinical | Register new patient |
| GET | `/patients/<id>` | Clinical | View patient details |
| GET | `/patients/<id>/records` | Clinical | View patient records |
| POST | `/records/diagnosis` | Doctor | Create diagnosis |
| POST | `/records/prescription` | Doctor | Create prescription |
| POST | `/records/vitals` | Nurse/Doctor | Record vitals |
| POST | `/records/lab-order` | Doctor | Order lab test |
| POST | `/admissions/create` | Clinical | Admit patient |
| POST | `/admissions/<id>/discharge` | Clinical | Discharge patient |
| POST | `/referrals` | Doctor | Create referral |
| GET | `/referrals/incoming` | Doctor | View incoming referrals |
| POST | `/consents` | Admin/Patient | Grant access to records |
| POST | `/break-glass` | Doctor | Emergency access (audited) |
| GET | `/admin/users` | Hospital Admin | List facility users |
| POST | `/admin/users/invite` | Hospital Admin | Invite new user |
| GET | `/admin/audit-logs` | Hospital Admin | View audit logs |
| GET | `/health` | Public | API health check |

---

## Best Practices

### Authentication
- **Token Storage:** Store JWT tokens in `sessionStorage` (not `localStorage`) to prevent persistence on shared devices
- **Refresh Strategy:** Automatically refresh access token on 401 response
- **Logout:** Always call `/auth/logout` to blacklist tokens; don't rely on client-side token deletion alone
- **MFA:** Support both authenticator apps and email OTP codes for resilience

### Error Handling
- **Retry Logic:** Implement exponential backoff for 503 errors; retry after `Retry-After` header seconds
- **User Messaging:** Show friendly messages; avoid exposing internal error details
- **Rate Limiting:** Respect `X-RateLimit-*` headers; implement client-side rate limit awareness

### Security
- **Hospital Scoping:** Never trust user input for hospital context; use server-side determination
- **Audit Logging:** All sensitive operations are logged server-side with full audit trail
- **Cross-Facility Access:** Always check consent/referral status; break-glass is emergency-only (15 min, audited)
- **HTTPS Only:** Always use HTTPS in production; never send credentials over HTTP

### Performance
- **Pagination:** Use limit/offset or cursor-based pagination for large result sets
- **Filtering:** Filter on server-side; don't fetch all data and filter client-side
- **Caching:** Patient searches can be cached locally for 60 seconds; refresh on patient admission/discharge
- **Batch Operations:** Use batch endpoints for bulk imports (see `/batch-import`)

---

## Support & Documentation

For more information:
- **Deployment:** See `docs/DEPLOYMENT.md`
- **Troubleshooting:** See `docs/TROUBLESHOOTING.md`
- **Architecture:** See `docs/Multi_Tenancy_Architecture.md`
- **Security:** See `medsync-backend/README.md` "Security" section

For assistance:
- **Email:** support@medsync.local
- **GitHub Issues:** https://github.com/kaacquah2/EMR/issues
