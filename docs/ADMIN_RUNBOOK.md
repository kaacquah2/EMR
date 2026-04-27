# MedSync EMR: Admin Runbook

**Status:** Production-Ready | **Version:** 1.0.0 | **Last Updated:** 2026-04-19

This document provides step-by-step procedures for Hospital Admins and Super Admins to manage MedSync EMR.

---

## Table of Contents

1. [Account Management](#account-management)
   - [Reset User Password](#reset-user-password)
   - [Reset MFA/Passkeys](#reset-mfapasskeys)
   - [Account Recovery Flow](#account-recovery-flow)
2. [Emergency Procedures](#emergency-procedures)
   - [Handle Break-Glass Access](#handle-break-glass-access)
   - [Audit Log Review](#audit-log-review)
3. [Hospital & Staff Onboarding](#hospital--staff-onboarding)
   - [Onboard New Hospital (Super Admin)](#onboard-new-hospital-super-admin)
   - [Onboard New Staff Member](#onboard-new-staff-member)
4. [Compliance & Reporting](#compliance--reporting)
   - [Generate Compliance Reports](#generate-compliance-reports)
   - [Handle Data Requests (GDPR/HIPAA)](#handle-data-requests-gdprhipaa)
5. [Troubleshooting](#troubleshooting)

---

## Account Management

### Reset User Password

**Use Case:** User forgot password or needs emergency reset after security incident.

#### Tier 1: User Self-Service (Via UI)

1. Direct user to login page: `https://app.medsync.health/login`
2. Click **"Forgot Password?"** link
3. User enters their email
4. System sends password reset link (valid for 24 hours)
5. User clicks link in email
6. User enters new password (must meet policy: 12+ chars, uppercase, lowercase, digit, symbol)
7. System verifies password is not reused from last 5 passwords
8. User logged in automatically (if MFA disabled) or prompted for TOTP

**Admin view:** Admins can monitor password resets in Audit Logs:
- Navigate: `/admin/audit`
- Filter: `action = "PASSWORD_RESET"`, `status = "success"`

#### Tier 2: Hospital Admin Reset (UI)

1. Navigate: `/admin/staff`
2. Find the staff member in the list
3. Click **"Actions"** → **"Reset Password"**
4. Confirm action
5. System generates temporary password and emails it to user
6. User logs in with temporary password, prompted to create new one
7. First login forces password change screen

**Process:**

```
Admin click "Reset Password"
  ↓
Send email: "Your MedSync password was reset by admin"
  ↓
Include temporary password (16 chars, 24-hour valid)
  ↓
User logs in with temp password
  ↓
Prompt: "Change password to continue"
  ↓
User enters new password (policy enforced)
  ↓
Verify not in last 5 password history
  ↓
Login success, redirect to dashboard
```

#### Tier 3: Super Admin Emergency Reset (Backend CLI)

For critical situations (staff account compromised):

```bash
# SSH into Railway backend or local dev:
python manage.py shell

from core.models import User
user = User.objects.get(email="staff@hospital.gh")

# Option A: Force password expiry (user sees reset prompt next login)
user.password_expires_at = timezone.now()
user.save()

# Option B: Set temporary password (admin provides via phone)
from django.contrib.auth.hashers import make_password
user.password = make_password("TempPass123!@#")
user.save()
# User must change on first login

# Log the action
from api.audit_logging import AuditLog
AuditLog.log_action(
    user=admin_user,
    action="PASSWORD_RESET_ADMIN",
    resource_type="User",
    resource_id=str(user.id),
    hospital=admin_user.hospital,
    details={"reset_reason": "emergency_security_incident"}
)
```

---

### Reset MFA/Passkeys

**Use Case:** User lost phone (TOTP), security key (passkey), or cannot access authenticator app.

#### Check User's MFA Status

**UI Path:** `/admin/staff`

```
Staff List → Find User → Click "View" or "Edit"
  ↓
Section: "Security"
  ├─ MFA Enabled: [Yes/No]
  ├─ MFA Last Verified: [date]
  ├─ Passkeys Registered: [1] [2] [3]
  │  └─ Device names and last used dates
  └─ Action buttons: [Reset MFA] [Reset Passkeys]
```

#### Tier 1: Self-Service MFA Reset

User navigates to: `/settings/security/mfa`

1. Click **"Disable MFA"**
2. System asks for current password (security check)
3. User enters password
4. MFA disabled
5. Next login: password only (no TOTP prompt)
6. User can re-enable at any time: **"Enable MFA"** → scan QR code with authenticator app → enter code to verify

#### Tier 2: Hospital Admin Reset MFA

1. Navigate: `/admin/staff`
2. Find user
3. Click **"Reset MFA"**
4. Confirm: "Reset MFA for John Doe? User will need to re-enroll."
5. System clears MFA secret and backup codes
6. Send email to user: "Your MFA was reset. Please re-enroll: [link]"
7. User can re-enroll via `/settings/security/mfa`

**Backup Code Handling:**

If user used backup code to login (e.g., phone lost), system generates new backup codes:

```
When MFA reset:
  ├─ Old TOTP secret invalidated
  ├─ All backup codes voided
  ├─ User prompted to re-setup
  ├─ Generate 10 new backup codes
  └─ Email codes in secure attachment (CSV)
```

#### Tier 2: Passkey Reset

1. Navigate: `/admin/staff`
2. Find user
3. Click **"Reset Passkeys"** or on user detail page, under "Security" section
4. Confirm: "Delete all passkeys for this user? They will not be able to login with biometric/security key."
5. System deletes all WebAuthn credentials
6. Send email: "Your passkeys were deleted. You can register new devices in Settings."
7. User must use password login until they enroll new passkey

**Process:**

```
Admin clicks "Reset Passkeys"
  ↓
Delete all WebAuthn credentials from DB
  ↓
Clear any cached passkey metadata
  ↓
Audit log: {action: "PASSKEY_RESET_ADMIN", user: admin_id, target_user: user_id}
  ↓
Email user with re-enrollment link
  ↓
User can add new passkeys anytime
```

---

### Account Recovery Flow

**Multi-layer recovery process:**

#### Step 1: Verify User Identity

Before resetting MFA or password:

1. **Email verification:** Confirm email address in system matches user identity
2. **Security questions (optional):** "What is your Ghana Health License number?"
3. **Admin confirmation:** Hospital admin manually verifies (phone call or in-person)

#### Step 2: Generate Recovery Code

System generates one-time recovery code (valid 1 hour):

```
Recovery Link: https://app.medsync.health/account-recovery?code=abc123xyz789
Sent via: Email + SMS (if phone on file)
Valid for: 1 hour
One-time use: Yes
```

#### Step 3: User Resets Account

User clicks link and:

1. Confirms identity (security question or backup code from file)
2. Sets new password
3. Re-enrolls in MFA
4. Clears passkeys (auto-prompted if any exist)
5. All active sessions logged out (for security)

#### Step 4: Audit Trail

All recovery actions logged:

```
AuditLog {
  action: "ACCOUNT_RECOVERY_INITIATED",
  user: "admin@hospital.gh",
  target_user: "staff@hospital.gh",
  details: {
    recovery_reason: "User_Requested" | "Admin_Initiated" | "Suspicious_Activity",
    verification_method: "email" | "security_question" | "admin_confirmation",
    timestamp: "2026-04-19T10:30:00Z"
  }
}
```

---

## Emergency Procedures

### Handle Break-Glass Access

**Use Case:** Investigate unauthorized emergency access or validate clinical necessity.

#### Step 1: Review Break-Glass Log Entry

**UI Path:** `/admin/audit` or `/admin/break-glass`

```
Filter: action = "BREAK_GLASS_INITIATED"
Find: User who triggered it, Patient accessed, Timestamp

Display Fields:
├─ User: Doctor Name (ID)
├─ Patient: Patient ID, Name (sanitized)
├─ Hospital: Hospital A (accessing)
├─ Reason: "Patient in critical condition..."
├─ Medical Justification: "Acute MI suspected..."
├─ Timestamp: 2026-04-19 10:15:30 UTC
├─ Expires: 2026-04-19 10:30:30 UTC (15 min window)
├─ Status: [active] [expired] [approved] [revoked]
└─ Action Buttons: [Approve] [Investigate] [Revoke]
```

#### Step 2: Verify Clinical Justification

1. Check if emergency was legitimate:
   - Is patient in ICU, emergency ward?
   - Did patient have adverse event?
   - Was the doctor authorized (MD license valid)?

2. Contact doctor if needed:
   - Call or message: "Can you confirm emergency access to patient [ID] on [date]?"
   - Request supporting documentation

3. Verify patient consent:
   - Was patient or family notified?
   - Is patient from another hospital (cross-facility)?

#### Step 3: Admin Decision

**Option A: Approve**

```
Click: [Approve]
Enter: Comments (optional)
Example: "Verified with ED physician. Appropriate emergency response."
Status: → APPROVED
Log Action: {action: "BREAK_GLASS_APPROVED", reviewed_by: admin_id, notes: "..."}
```

**Option B: Revoke (Suspicious)**

```
Click: [Revoke]
Reason: Select from dropdown or enter custom
├─ Unauthorized Access
├─ Policy Violation
├─ Credentials Compromised
├─ Other (require comment)

Optional: Notify user
Example: "Your emergency access to patient X was reviewed and revoked. Please contact admin."

Audit: {action: "BREAK_GLASS_REVOKED", reviewed_by: admin_id, reason: "..."}
```

#### Step 4: Escalation

If suspicious pattern detected:

1. **Count break-glass events by user (last 7 days):**
   - Normal: 0-2 per week
   - Suspicious: > 5 per week
   - Critical: 10+ per week

2. **Alert Super Admin:** "User [name] has triggered 8 break-glass accesses in 3 days. Recommend investigation."

3. **Temporary Suspension (Super Admin Only):**
   ```
   Revoke all active break-glass sessions
   Disable break-glass capability for 24 hours
   Require security training before re-enabling
   Log all changes with reason
   ```

---

### Audit Log Review

**Use Case:** Investigate suspicious activity, compliance audit, or data breach investigation.

#### Access Audit Logs

**UI Path:** `/admin/audit`

```
Filters Available:
├─ Date Range: [From] [To]
├─ Action: [Dropdown] CREATE, UPDATE, DELETE, VIEW, VIEW_CROSS_FACILITY, BREAK_GLASS, LOGIN, LOGOUT, etc.
├─ Resource Type: [Dropdown] Patient, Encounter, Prescription, LabOrder, etc.
├─ User: [Search] user@hospital.gh
├─ Hospital: [Dropdown] Hospital A, Hospital B
├─ Status: [Dropdown] Success, Error
├─ IP Address: [Search]
└─ [Apply Filters]

Results Table:
├─ Timestamp (sortable)
├─ User (link to profile)
├─ Action
├─ Resource Type / ID
├─ Hospital
├─ Status
└─ [View Details]
```

#### Common Investigations

##### 1. Who accessed a patient's records?

```
Filter:
├─ Resource Type: Patient
├─ Action: VIEW
├─ Date Range: [last 30 days]
└─ [Apply]

Results show all views of that patient (patient_id in resource_id field)
Click [View Details] to see:
├─ User: doctor@hospitalB.gh
├─ IP: 192.168.1.100
├─ User Agent: Mozilla/5.0 Chrome/120
├─ Consent Scope: FULL_RECORD (if cross-facility)
├─ Referral ID: ref-abc123 (if via referral)
└─ Timestamp: 2026-04-19 14:30:00 UTC
```

##### 2. Find all modifications to a patient's diagnoses (last 24 hours)

```
Filter:
├─ Action: CREATE, UPDATE, DELETE
├─ Resource Type: Diagnosis
├─ Date Range: [Yesterday 00:00 to Today 00:00]
└─ [Apply]

Results show diagnosis create/update/delete events
Verify: User authorized, timestamp aligns with clinical shift, no midnight changes (suspicious)
```

##### 3. Detect break-glass abuse

```
Filter:
├─ Action: BREAK_GLASS_INITIATED
├─ Date Range: [Last 7 days]
└─ [Apply]

Identify patterns:
├─ User X: 8 initiations (suspicious if only 1-2 legitimate emergencies expected)
├─ Same patient accessed 3x in 2 hours (sign of curiosity, not emergency)
└─ Access after hours + no ED activity (flag for review)

Action:
├─ Click user name → View user profile
├─ Check role: Is this user authorized for break-glass (doctor, nurse)?
├─ Check hospital assignment: Can this user access patients from other hospitals?
└─ Escalate to Super Admin if credentials seem compromised
```

##### 4. Login anomalies

```
Filter:
├─ Action: LOGIN
├─ Status: Error
├─ Date Range: [Last 24 hours]
└─ [Apply]

Identify:
├─ Failed login attempts (> 5 from same user in 1 hour = brute-force attempt)
├─ Unusual IP addresses: Is 192.0.2.1 from USA but user is in Ghana?
├─ Unusual time: Login at 03:00 AM when user usually works 9-5

Action:
├─ If brute-force: Account temporarily locked (automated or manual)
├─ If unusual IP: Email user "Login attempt from [IP], [location]. Not you? Reset password."
├─ If multiple IPs same user: Possibly shared login (security violation) → Investigate
```

---

## Hospital & Staff Onboarding

### Onboard New Hospital (Super Admin)

**Use Case:** Add a new hospital facility to the MedSync network.

#### Step 1: Create Hospital Record

**UI Path:** `/admin/hospitals` (Super Admin only)

```
Click: [Add Hospital]
Form Fields:
├─ Hospital Name: [Text] "Korle Bu Teaching Hospital"
├─ Hospital Code: [Code] "KBU" (3-5 chars, unique)
├─ Region: [Dropdown] Greater Accra, Ashanti, Western, etc.
├─ District: [Text] "Accra"
├─ Address: [Text] "Korle Bu, Accra, Ghana"
├─ Contact Email: [Email] "admin@korlebu.gh"
├─ Contact Phone: [Phone] "+233 30 266 0000"
├─ Hospital Website: [URL] "https://korlebu.edu.gh"
├─ License Number: [Text] "HC-2024-001" (regulatory ID)
├─ Bed Capacity: [Number] 500
├─ FHIR Endpoint (optional): [URL] "https://korlebu.edu.gh/fhir" (for HIE)
└─ [Create Hospital]
```

#### Step 2: Create Ward Structure

After hospital created:

1. Navigate: `/admin/hospitals/<hospital_id>/wards`
2. Click: [Add Ward]
3. For each ward/department:
   ```
   Ward Name: "Cardiology"
   Bed Capacity: 30
   Chief Nurse (optional): [Search & Select]
   Description: "Cardiac care and monitoring"
   ```

#### Step 3: Configure Hospital Admin User

1. Navigate: `/admin/staff`
2. Click: [Invite Staff]
3. Form:
   ```
   Email: admin@korlebu.gh
   First Name: John
   Last Name: Appiah
   Role: [Dropdown] → Select "hospital_admin"
   Hospital: [Dropdown] → Select "Korle Bu Teaching Hospital"
   Ward: [Leave blank for admins]
   ```
4. Send invitation (email delivered automatically)
5. Hospital Admin receives email with signup link (valid 72 hours)
6. Admin clicks link, sets password, enrolls MFA
7. Can now login and manage their hospital's staff

#### Step 4: Create Initial Staff

Hospital Admin now creates base team:

```
Hospital Admin navigates: /admin/staff
Creates staff by role:
├─ Doctors (1-5): role = "doctor"
├─ Nurses (3-10): role = "nurse"
│  └─ Assign to Ward (e.g., "Cardiology")
├─ Lab Techs (1-3): role = "lab_technician"
├─ Receptionists (1-2): role = "receptionist"
└─ Other Admins (optional): role = "hospital_admin"
```

#### Step 5: Integration

- Hospital is now active in system
- Receptionists can register patients (ghana_health_id will be unique per hospital)
- Doctors can see their patients and create encounters
- HIE enabled: Can create consents/referrals to other hospitals

#### Step 6: Audit Trail

All onboarding logged:

```
AuditLog entries:
├─ {action: "CREATE", resource: "Hospital", hospital_id: "new_hospital_id", created_by: "super_admin_id"}
├─ {action: "CREATE", resource: "Ward", hospital_id: "new_hospital_id", ...}
├─ {action: "INVITE", resource: "User", email: "admin@korlebu.gh", role: "hospital_admin"}
└─ {action: "ACTIVATE", resource: "Hospital", status: "active"}
```

---

### Onboard New Staff Member

**Use Case:** Add a new doctor, nurse, or other clinical staff to a hospital.

#### Method 1: Hospital Admin Invites (Standard)

1. Navigate: `/admin/staff`
2. Click: [Invite Staff]
3. Fill form:
   ```
   Email: doctor@korlebu.gh
   First Name: Mary
   Last Name: Asante
   Role: [Dropdown]
   └─ If "nurse": Also select Ward assignment
   Hospital: Auto-populated (can't change for non-super-admin)
   ```
4. Click: [Send Invitation]
5. System sends email with signup link (valid 72 hours)
6. Recipient clicks link:
   - Set password (policy enforced)
   - Enroll MFA (optional, can skip)
   - Accept terms
   - Redirect to dashboard
7. Staff member active, can access assigned area

#### Method 2: Bulk Import (Hospital Admin)

For onboarding many staff at once:

```
Navigate: /admin/staff/bulk-import
Upload: CSV file with columns:

email,first_name,last_name,role,ward_name
doctor1@hospital.gh,John,Appiah,doctor,
doctor2@hospital.gh,Mary,Asante,doctor,
nurse1@hospital.gh,Jane,Agyeman,nurse,Cardiology
nurse2@hospital.gh,Kwame,Osei,nurse,Cardiology
lab1@hospital.gh,Samuel,Mensah,lab_technician,
receptionist1@hospital.gh,Ama,Boateng,receptionist,

Validation:
├─ Email unique? (required)
├─ Role valid? (from enum)
├─ Ward exists? (if nurse, ward_name must match)
└─ [Proceed] or [Cancel]

Result:
├─ All valid staff invited
├─ Emails queued
├─ Error report for invalid rows
└─ Audit log: {action: "BULK_IMPORT", count: 6, hospital_id: "..."}
```

#### Step 3: Verify Active Status

Hospital Admin checks staff list after 24 hours:

```
Navigate: /admin/staff
Status column shows:
├─ ✓ Active: Doctor Mary Asante (logged in 2 hours ago)
├─ ⏳ Pending: Nurse Jane Agyeman (invitation sent 20 hours ago, not yet signup)
├─ ✗ Expired: Dr. Unknown (invitation sent 4 days ago, never used link)

Actions:
├─ Pending: [Resend Invitation] [Cancel]
├─ Active: [Edit] [Reset MFA] [Deactivate]
└─ Expired: [Delete] [Resend]
```

---

## Compliance & Reporting

### Generate Compliance Reports

**Use Case:** Monthly reports for regulatory compliance (HIPAA, GDPR).

#### Report Types Available

**1. Access Log Report** (HIPAA Requirement §164.308)

```
Navigate: /admin/compliance/reports
Report: "Access Log Report"
Date Range: [Month] [Year]
Hospital: [Dropdown] Select hospital(s)

Generate → PDF/CSV

Contains:
├─ Total data access events
├─ Breakdown by role (Doctor: 450, Nurse: 320, Lab: 180, etc.)
├─ Top 10 most-accessed patients
├─ Cross-facility accesses (with consent scope)
├─ Break-glass events (with justification)
├─ Unauthorized access attempts (blocked/errors)
└─ Top 10 users by access volume

Example Output:
═════════════════════════════════════════════════════════
ACCESS LOG REPORT - March 2026
Hospital: Korle Bu Teaching Hospital
═════════════════════════════════════════════════════════

SUMMARY:
  Total Accesses: 12,450
  Success Rate: 99.2%
  Errors/Denied: 98
  Cross-Facility: 234
  Break-Glass Events: 8

BY ROLE:
  Doctors: 6,200 (49.8%)
  Nurses: 3,100 (24.9%)
  Lab Techs: 1,800 (14.4%)
  Receptionists: 900 (7.2%)
  Admins: 450 (3.6%)

CROSS-FACILITY ACTIVITY:
  From Hospital A (Incoming): 120
    └─ Scope: FULL_RECORD (100), SUMMARY (20)
  To Hospital B (Outgoing): 114
    └─ Scope: FULL_RECORD (95), SUMMARY (19)

BREAK-GLASS EVENTS:
  User: Dr. Emmanuel Owusu
    Patient: GH-2024-001234
    Date: 2026-03-15 14:30 UTC
    Reason: "Acute cardiac event, patient unconscious"
    Justification: "Critical patient from referral hospital"
    Status: APPROVED by Compliance Officer
```

**2. Data Breach Incident Report**

```
If no incidents: "No data breaches detected this period"

If incidents found:
├─ Incident Date
├─ Type: Unauthorized Access | Loss of Device | Misconfigured Settings | etc.
├─ Severity: Low | Medium | High | Critical
├─ Users Affected
├─ Data Affected (de-identified patient count)
├─ Root Cause
├─ Response Timeline
├─ Resolution
└─ Preventive Measures Taken

Actions:
  [Notify Regulator] (if required by law)
  [Notify Patients] (if risk to privacy)
  [Close Incident]
```

**3. Consent & Referral Report**

```
Report: "Cross-Facility Data Sharing"
Date Range: [Month] [Year]

CONSENT SUMMARY:
  Active Consents: 45
  Expired Consents: 12
  Revoked Consents: 3
  Total Patient Records Shared: 523

BREAKDOWN:
  Granted BY Korle Bu TO:
    └─ Achimota Hospital: 25 (scope: FULL_RECORD 20, SUMMARY 5)
    └─ Ridge Hospital: 18 (scope: FULL_RECORD 15, SUMMARY 3)
  
  Granted TO Korle Bu FROM:
    └─ Achimota: 30 (accesses this month: 45)
    └─ Ridge: 25 (accesses this month: 38)

REFERRAL ACTIVITY:
  Outgoing Referrals: 8
    Status: Pending 2, Accepted 5, Rejected 1
  Incoming Referrals: 6
    Status: Pending 1, Accepted 4, Completed 1
```

**4. MFA Compliance Report**

```
Report: "Multi-Factor Authentication Status"

MFA ENROLLMENT:
  Total Staff: 125
  MFA Enabled: 118 (94.4%)
  MFA Disabled: 7 (5.6%)
    └─ Reason (from user settings): Not required (6), Device lost (1)

PASSKEY ENROLLMENT:
  Total Passkeys Registered: 89 (across 76 users)
  Average per User: 1.2
  Device Types:
    └─ Windows Hello: 45
    └─ iOS Face ID: 28
    └─ Security Key (FIDO2): 16

EXCEPTIONS (Flagged):
  Staff Without MFA:
    ├─ Receptionist A: No MFA (reason: "New hire, pending enrollment")
    └─ Admin B: MFA disabled (reason: "Security incident investigation")

ACTION REQUIRED:
  [x] Contact staff without MFA to enroll within 7 days
  [x] Review admin MFA status
```

**5. Audit Trail Export** (For external auditors)

```
Format: CSV (Excel-friendly)
Columns:
├─ Timestamp
├─ User ID (de-identified)
├─ Action
├─ Resource Type
├─ Resource ID (sanitized, no PHI)
├─ Hospital
├─ IP Address
├─ Status (Success/Error)
├─ Error Message (if any)
└─ Details (JSON)

File Size: ~5 MB per month (12,000 entries)
Security: Encrypted PDF with password, separate email
```

---

### Handle Data Requests (GDPR/HIPAA)

**Use Case:** User or regulator requests access to all data held about a person (subject access request).

#### Step 1: Receive Request

**Sources:**
- Patient submits request via support@medsync.health
- Regulator (DPA, FDA) requests via formal channel
- Staff member requests own data

**Standard Form:**

```
DATA SUBJECT ACCESS REQUEST

Name: [Person Name]
Email: [Contact]
Ghana Health ID: [ID] or DOB: [Date]
Scope: "All data held about me" or "Specific records" (patient records only, claims, etc.)
Reason (optional): "GDPR Right of Access", "Account Deletion Prep", etc.

INSTRUCTIONS:
1. MedSync will respond within 30 days (GDPR requirement)
2. You will receive a secure download link (valid 7 days)
3. Data exported in standard format (PDF/CSV)
4. No cost to requester
5. Questions: support@medsync.health
```

#### Step 2: Verify Identity

**For Patient Request:**

1. Check that email matches registered account OR
2. Request secondary verification:
   - Ghana Health ID + DOB (from registration)
   - Last 4 digits of phone on file
   - Security question (if on file)

**For Regulator Request:**

1. Verify request contains official letterhead/seal
2. Contact regulator's office to confirm authenticity
3. Check request contains sufficient identification (case number, etc.)

**For Staff Request:**

1. Verify user is authenticated (logged in)
2. Can request own data anytime (no verification needed)

#### Step 3: Generate Data Export

**UI Path:** `/admin/data-exports` (Super Admin / Hospital Admin)

```
Click: [New Request]
Form:
├─ Request Type: [Dropdown]
│  ├─ Patient (GDPR/HIPAA Subject Access)
│  ├─ Staff Member (Own Data)
│  ├─ Regulator (Subpoena/Formal Request)
│  └─ Other (specify)
├─ Subject: [Email or ID]
├─ Date Range: [From] [To] (default: all history)
├─ Include: ☑ Clinical Records
│           ☑ Appointments
│           ☑ Lab Results
│           ☑ Audit Logs (admin only)
│           ☑ Communications (if any)
└─ Format: [Dropdown] PDF | CSV | XML

Click: [Generate]
```

**System exports all data:**

```
Patient John Doe (GH-2024-001234):

DEMOGRAPHICS:
├─ Name: John Doe
├─ DOB: 1985-05-15
├─ Gender: Male
├─ Ghana Health ID: GH-2024-001234
└─ Registered: 2024-01-10

ENCOUNTERS (12 total):
├─ 2026-03-15 14:30 UTC
│  ├─ Type: Outpatient
│  ├─ Provider: Dr. Mary Asante
│  ├─ Chief Complaint: Headache and fever
│  ├─ Diagnoses: Migraine (G43.1), Fever (R50.9)
│  ├─ Prescriptions: Paracetamol 500mg x3 daily
│  └─ Vitals: BP 120/80, HR 72, Temp 37.2°C
└─ [Earlier encounters...]

APPOINTMENTS (5 total):
├─ 2026-04-10 09:00 - Dr. Emmanuel Owusu (Scheduled)
└─ [Earlier appointments...]

LAB ORDERS & RESULTS (8 total):
├─ 2026-03-10: Full Blood Count
│  ├─ Results: WBC 7.2, RBC 4.8, Hb 14.5
│  └─ Status: Completed
└─ [Earlier tests...]

AUDIT LOG (showing only own profile access):
├─ 2026-04-19 10:15 - Login successful (IP: 192.168.1.100)
├─ 2026-04-19 10:16 - View own profile
└─ [Other activity...]
```

#### Step 4: Encrypt & Secure Delivery

```
System generates:
├─ PDF file (all records formatted nicely, images embedded)
├─ Encrypts PDF with password: [Random 16-char password]
├─ Stores encrypted file on S3 (temp folder)
├─ Generates secure download link (valid 7 days)

Email to requester:
┌──────────────────────────────────────────────────┐
│ Subject: Your MedSync Data Export - Ready        │
│                                                  │
│ Dear John Doe,                                   │
│                                                  │
│ Your data export is ready. Download below.       │
│                                                  │
│ DOWNLOAD: [Secure Link]                         │
│ (Link expires in 7 days)                         │
│                                                  │
│ PASSWORD: [Provided separately via SMS/phone]    │
│                                                  │
│ File contains:                                   │
│ - All clinical records                          │
│ - Appointments and encounters                   │
│ - Lab results                                   │
│ - Your own profile data                         │
│                                                  │
│ Questions: support@medsync.health                │
│ Prepared: 2026-04-19 15:30 UTC                   │
│ Request ID: REQ-2026-001234                     │
└──────────────────────────────────────────────────┘
```

#### Step 5: Right to Deletion (GDPR)

If requester asks to delete their data:

```
REQUEST: "Delete all my data"

RESPONSE (Admin):
Cannot fully delete patient medical records (required for audit trail, 7-year retention).

Can delete:
├─ Profile (name, contact info) → De-identify records
├─ Appointment history → Archive
├─ Personal preferences/settings
└─ Communications

Retained (legally required):
├─ Clinical records (audit trail)
├─ Medication history (drug interactions)
├─ Lab results (continuity of care)
└─ Audit log (compliance)

Inform patient:
"We can de-identify your personal information and archive historical records.
Clinical data is retained per healthcare regulations (7 years) but will not
be accessible to new staff unless clinically relevant."

Process:
1. Mark account as "pseudonymized"
2. Replace name with randomly-generated ID
3. Remove contact info
4. Archive non-critical files
5. Log action: {action: "DATA_PSEUDONYMIZATION", user_id: "...", date: "2026-04-19"}
```

---

## Troubleshooting

### Common Issues

#### Issue: User locked out (too many failed login attempts)

```
Symptom: "Your account is temporarily locked. Try again in 15 minutes."

Root Cause:
- User entered wrong password 10+ times in 1 hour
- Brute-force protection activated
- Account auto-locked for 15 minutes

Resolution:
1. User waits 15 minutes, tries again
2. Or: Admin manually unlocks (without re-requesting password)
   - Navigate: /admin/staff
   - Find user
   - Click [Unlock Account]
   - Confirm
   - Status: "Unlocked"
3. Or: User resets password via "Forgot Password" (bypass account lock)

Prevent: Implement rate limiting on login form (frontend + backend)
```

#### Issue: Patient registration failing (Ghana Health ID already exists)

```
Symptom: "Ghana Health ID GH-2024-001234 already registered"

Root Cause:
- Same patient registered twice (duplicate)
- Different hospital mistakenly used same ID

Resolution:
1. Check: Is this truly the same patient (same DOB, name)?
   - Yes → Merge records (see Merge Data below)
   - No → Generate new ID

2. Manual ID Assignment:
   - Receptionist retries, system generates new unique ID
   - Or: Admin manually assigns next available ID

3. Merge Duplicate Records:
   - Super Admin only
   - Navigate: /admin/data-management/merge
   - Select primary record (to keep)
   - Select secondary record (to merge into primary)
   - Select merge strategy (keep primary's appointment, combine lab results, etc.)
   - System merges and updates all encounters, diagnoses, etc.
   - Audit log: {action: "PATIENT_MERGE", primary: "...", secondary: "...", merged_by: "admin_id"}

Prevent: Validate patient before registration (check DOB + name match before auto-confirm)
```

#### Issue: Slow API responses (encounters, patient list loading slow)

```
Symptom: Dashboard takes 10+ seconds to load, encounter creation hangs

Root Cause:
- Database query not indexed
- Too many JOIN operations
- Large dataset (millions of records)

Troubleshooting:
1. Check Django Slow Query Logs:
   - Production: Review Application Performance Monitoring (APM) tool
   - Dev: Enable django-silk or query logging
   - Look for queries > 1 second

2. Identify problem endpoint:
   - Slow list API: GET /patients → likely missing index on hospital_id
   - Slow create: POST /encounters → likely trigger or constraint check

3. Fix:
   a) Add database index:
      CREATE INDEX idx_patient_hospital ON patients(hospital_id);
      
   b) Optimize query (DRF serializer):
      - Use select_related() for ForeignKey
      - Use prefetch_related() for ManyToMany
      
   c) Reduce data:
      - Paginate results (cursor-based)
      - Limit fields returned (sparse fieldsets)

4. Verify fix:
   - Reload page, measure response time
   - Target: p95 < 500ms
```

#### Issue: MFA code not working (TOTP error)

```
Symptom: "Invalid code" after entering TOTP from authenticator app

Root Cause:
1. Clock skew: User's phone clock is out of sync with server
2. Wrong app: User enrolled in wrong authenticator app
3. TOTP secret not properly stored
4. Code already used (TOTP is time-based, 30-sec validity)

Resolution (User):
1. Sync phone time:
   - iPhone: Settings → General → Date & Time → Auto set (on)
   - Android: Settings → Date & Time → Automatic (on)
2. Wait 30 seconds, try new code
3. Try backup code instead (if phone enrolled)
   - Check email for backup codes

Resolution (Admin):
1. If user still can't login:
   - Reset MFA: /admin/staff → [Reset MFA]
   - User re-enrolls
2. Or: Issue temporary password (admin tier 3 reset)

Prevention:
- On MFA enrollment: Show 3 test codes to verify before confirming
- Display: "Sync your device time before enrolling"
```

#### Issue: Cross-facility patient not appearing (consent not working)

```
Symptom: "Patient not found" in Hospital B, even though Hospital A granted consent

Root Cause:
- Consent not yet created/active
- Consent has SUMMARY scope only (demographics hidden)
- Consent expired
- User's role doesn't allow cross-facility access

Verification:
1. Check consent exists:
   - Hospital A admin: /hie/consents
   - Find patient in "granted_to" column
   - Status: [Active] [Expired] [Revoked]

2. Check consent scope:
   - SUMMARY: Can see name, DOB, contact (demographics only)
   - FULL_RECORD: Can see all records (diagnoses, prescriptions, labs, notes)

3. Check user role:
   - Doctors / Nurses: Can access (with consent)
   - Receptionists: Cannot access cross-facility (restricted role)

4. Check date:
   - Consent expires: 2026-03-15
   - Today: 2026-04-19
   - Status: EXPIRED
   - Action: Ask Hospital A to extend or create new consent

Fix:
Hospital A doctor:
  Navigate: /hie/consents
  Find consent to Hospital B
  Click: [Extend] or [Renew]
  Set new expiry date
  Confirm

Hospital B can now search & access
```

---

## Additional Resources

- **Audit Logging Guide:** See `/docs/AUDIT_LOGGING.md`
- **Security Policy:** See `/docs/SECURITY_POLICY.md`
- **Compliance Requirements:** See `/docs/COMPLIANCE.md`
- **API Documentation:** See `/docs/OPENAPI_SETUP.md` or `/api/schema/swagger-ui/`

---

**For critical issues, contact:**
- **Level 1 Support:** support@medsync.health (Mon-Fri 09:00-17:00 WAT)
- **Level 2 Support:** oncall@medsync.health (24/7 emergency)
- **Super Admin Emergency:** Contact platform team directly (contact info in secure channel)
