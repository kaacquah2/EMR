# Demo runbook

## Start

1. Run `make demo`.
2. Open `http://localhost:3000/login`.
3. If needed, check backend at `http://localhost:8000/api/v1/health`.

## Opening pitch

Most EMR systems use blanket MFA, which clinical staff often bypass because it interrupts care. This system uses risk-based adaptive authentication instead: low-risk routine access is frictionless, and high-risk actions such as cross-hospital record access trigger a step-up challenge at the moment of action.

## Demo accounts

Use the seeded accounts from `setup_dev`:

| Role | Email | Password |
| --- | --- | --- |
| Doctor | `doctor@medsync.gh` | `Doctor123!` |
| Nurse | `nurse@medsync.gh` | `Nurse123!@#` |
| Hospital admin | `hospital_admin@medsync.gh` | `HospitalAdmin123!` |
| Super admin | `admin@medsync.gh` | `Admin123!@#` |

## Patient for referral demo

Use **Comfort Acheampong** (`GH-2018-442229`, `PAT-00001`) from `load_demo_patients`.

## Walkthrough

1. **Normal login — no MFA challenge**
   Sign in as the nurse on the demo device. Because it is a known device within hours, login completes immediately. Explain that this is intentional for a trusted hospital workstation.

2. **First login from a new device — Tier 2 fires**
   Open an incognito window, sign in as the doctor, and enter the email OTP challenge. Explain that the new device is treated as higher risk, so the system requires second-factor verification and then trusts that device for future logins.

3. **Cross-hospital access — Tier 3 step-up**
   As the authenticated doctor, open a cross-hospital patient record. The system should prompt for step-up verification at the moment of access. After verification, show the access decision and explain that this action is always challenged regardless of session age.

3b. **Consent scope enforcement — SUMMARY vs FULL_RECORD**
    
   This scenario demonstrates how consent scopes control cross-facility access:
    
   **Setup:**
   - Use two hospitals: Hospital A (where Comfort Acheampong is registered) and Hospital B.
   - Sign in as a Hospital A doctor who has access to Comfort's full record.
   - Have a Hospital B doctor sign in separately (or use a different browser/tab).
    
   **Step 1: Grant SUMMARY consent**
    
   1. As the Hospital A doctor, navigate to Comfort Acheampong's record.
   2. Open the "Sharing" or "Cross-Facility Consent" panel.
   3. Grant consent to **Hospital B** with scope **SUMMARY**.
   4. Backend action: POST `/api/v1/consents` with `scope=SUMMARY`.
   5. Audit log entry: ACTION=CONSENT_GRANT, resource_type=GlobalPatient.
    
   **Step 2: Verify SUMMARY returns demographics only**
    
   1. Sign in as the Hospital B doctor (or switch to the Hospital B session).
   2. Navigate to the patient search or cross-facility access endpoint.
   3. Search for or access Comfort Acheampong's record by global patient ID.
   4. Frontend action: GET `/api/v1/cross-facility-records/<GPID>/`.
   5. Expected result: The response includes only demographics (name, DOB, Ghana Health ID, contact info). Clinical notes, diagnoses, prescriptions, and vitals are **NOT** included.
   6. Confirm: Open the browser DevTools → Network tab → filter for `cross-facility-records` and verify the response payload has no clinical data.
    
   **Step 3: Upgrade to FULL_RECORD consent**
    
   1. As the Hospital A doctor, return to Comfort's sharing panel.
   2. Find the existing Hospital B SUMMARY consent.
   3. Edit or revoke it and grant a new consent with scope **FULL_RECORD**.
   4. Backend action: POST `/api/v1/consents` with `scope=FULL_RECORD` (or DELETE the old consent and POST a new one).
   5. Audit log entry: ACTION=CONSENT_REVOKED and then ACTION=CONSENT_GRANT.
    
   **Step 4: Verify FULL_RECORD returns clinical notes**
    
   1. As the Hospital B doctor, reload the same patient record (or make a fresh GET to `/api/v1/cross-facility-records/<GPID>/`).
   2. Expected result: The response now includes all clinical data — diagnoses, prescriptions, vital signs, lab results, nursing notes, and medical history.
   3. Confirm: Open the same DevTools network tab and compare the payload size and content to Step 2. You should see clinical entries that were previously absent.
   4. Explain: "The same record, different permission levels. SUMMARY is for emergency reference only; FULL_RECORD is for continuity of care."

4. Sign out and sign in as the hospital admin to review `http://localhost:3000/referrals`.
5. Sign in as the nurse and attempt a forbidden action (negative test): try to create a referral via POST `/api/v1/referrals` and observe HTTP 403 — this proves RBAC prevents nurses from creating referrals.
6. Sign in as the super admin and open `http://localhost:3000/superadmin/audit-logs`.

## Notes on seeding demo data

- The seed file `medsync-backend/data/seeds/demo_patients.json` contains Comfort Acheampong (GH-2018-442229). To load this patient into an existing demo hospital, run:

  ```bash
  # Replace <hospital-id> with your hospital UUID (from setup_dev output or from the admin list)
  docker-compose exec backend python manage.py load_demo_patients --file=medsync-backend/data/seeds/demo_patients.json --hospital-id=<hospital-id>
  ```

- If using `setup_dev` to create hospitals and users, note the demo seed references `demo-gh-001`. If you prefer, pass the hospital id shown by setup_dev to the load_demo_patients command as shown above.

## cURL examples (Consent SUMMARY -> FULL_RECORD)

1) Grant SUMMARY consent (doctor or hospital_admin action):

```bash
curl -X POST http://localhost:8000/api/v1/consents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"global_patient_id":"<GPID>", "granted_to_facility":"<TARGET_FACILITY_ID>", "scope":"SUMMARY"}'
```

2) Verify only demographics visible (cross-facility record endpoint):

```bash
curl -X GET "http://localhost:8000/api/v1/cross-facility-records/<GPID>/" -H "Authorization: Bearer $ACCESS_TOKEN"
```

3) Grant FULL_RECORD consent and re-check:

```bash
curl -X POST http://localhost:8000/api/v1/consents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"global_patient_id":"<GPID>", "granted_to_facility":"<TARGET_FACILITY_ID>", "scope":"FULL_RECORD"}'
```

Then re-run the cross-facility-records GET and observe clinical notes returned.

## Order

1. Trusted nurse login
2. New-device doctor login
3. Cross-hospital step-up
4. Consent scope demo
5. Nurse negative test
6. Super admin audit review

---

## Ward Clerk Dashboard Demo

MedSync provides a dedicated console for the **Ward Clerk** (`ward_clerk`) role focused on bed management, admissions allocation, and transfers:

1. **Sign in as Ward Clerk:**
   - Use a seeded account or create one under the Ward Clerk role assigned to a specific ward.
   - Upon login, the clerk is redirected to the **Ward Administration & Bed Management** dashboard.
2. **Bed Status Management:**
   - Vacant beds display their current status. The clerk can mark a bed as "Maintenance" (taken out of active allocation) or click "Mark Ready" to return it to "Available".
3. **Patient Bed Transfers:**
   - For occupied beds, the clerk can click "Transfer" to re-assign the patient to any available vacant bed in their ward. This invokes `POST /api/v1/admissions/<id>/transfer` on the backend.
4. **Admissions Worklist & Allocation:**
   - When a patient is admitted to the ward (e.g. by a doctor or receptionist) without a bed assigned, they appear in the "Unassigned Admissions" worklist.
   - The clerk can click "Allocate Bed" and choose a vacant available bed to assign them to.

---

## Radiology Technician & DICOM Scope

> [!NOTE]
> **Out of Scope Notice:**
> The role `radiology_technician` is defined in the system's role directories and backend RBAC matrices for future capability expansion. However, a dedicated radiology execution module, DICOM viewer/image integration, and technician-specific workflows are **out of scope** for this release and have no corresponding frontend UI dashboards. Radiology orders are generated by doctors and attachments are handled via generic document uploads.

---

## Email MFA & SMTP Demo Configuration

To successfully perform the "new device login" flow with actual email delivery during your demo:

1. Copy `medsync-backend/.env.example` to `medsync-backend/.env` (if you haven't already).
2. Configure a real or sandbox SMTP provider in your `.env` file (see details in [medsync-backend/README.md](file:///c:/Users/OSCARPACK/Downloads/EMR/medsync-backend/README.md)). 
   - **Mailtrap** is recommended for easy testing as it captures outbound messages in a secure developer inbox.
   - Alternatively, you can use **SendGrid** or **Mailgun** API credentials.
3. Once configured:
   - Log in using a demo account (e.g., `doctor@medsync.gh`) in an Incognito browser window.
   - Check your SMTP/Mailtrap inbox for the MFA OTP verification code.
   - Enter the code on the login page to complete authentication.


