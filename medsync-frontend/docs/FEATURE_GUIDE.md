# MedSync Feature User Guide

**Purpose:** Role-based guide to using MedSync features effectively. Designed for clinicians and staff with varying technical backgrounds.

**Version:** 1.0  
**Last Updated:** 2025

---

## Table of Contents

1. [Doctor](#doctor)
2. [Nurse](#nurse)
3. [Lab Technician](#lab-technician)
4. [Receptionist](#receptionist)
5. [Hospital Administrator](#hospital-administrator)
6. [Super Admin / System Administrator](#super-admin--system-administrator)

---

## Doctor

### Overview

As a doctor, you'll use MedSync to:
- **Search and view patient records** across all your hospital's patients
- **Create and manage encounters** (patient visits)
- **Order lab tests and medications**
- **Use AI-powered clinical decision support** to analyze patient risk
- **Create diagnoses and treatment plans**
- **Manage referrals** to other hospitals
- **View cross-facility records** (with consent)
- **Access break-glass emergency records** (when needed)

### Key Features

#### 1. Patient Search and Registration

**Scenario:** Patient Kwame Owusu walks in. You need to find him or register him if new.

**Steps:**
1. Click **"Patients"** in left sidebar
2. Click **"Search"** button
3. Type patient name, Ghana Health ID, NHIS number, or phone
4. Results show within 2 seconds
5. Click patient name to view full record

**To Register New Patient:**
1. Click **"+ New Patient"** button
2. Fill required fields:
   - Full name (required)
   - Date of birth (required) — Format: YYYY-MM-DD
   - Gender (required)
   - Blood group (optional but recommended)
   - Phone number (optional)
   - NHIS/Insurance number (optional)
3. Click **"Register"**
4. System auto-generates Ghana Health ID
5. Patient now searchable in system

**Tips:**
- Always enter phone number if available (for follow-up)
- Use "Duplicate Check" before registering to avoid duplicates
- If patient is from another hospital, consent may be required to view full records

---

#### 2. Create Encounter (Patient Visit)

**Scenario:** Patient arrived for follow-up. You need to document the visit.

**Steps:**
1. Search and open patient record
2. Click **"New Encounter"** button (blue button in top-right)
3. System auto-fills:
   - Patient name
   - Your name as provider
   - Current timestamp
   - Your hospital
4. Fill encounter details:
   - **Chief Complaint:** Why patient came (e.g., "Hypertension follow-up")
   - **Findings:** Physical exam results (e.g., "BP 120/80, pulse 72")
   - **Assessment:** Your clinical impression (e.g., "Hypertension well-controlled")
   - **Plan:** Next steps (e.g., "Continue current meds, follow-up in 1 month")
5. Draft auto-saves every 30 seconds (see "Draft Auto-Saved at 14:35")
6. Click **"Save as Draft"** to save without closing
7. Click **"Close Encounter"** when done to lock record

**Encounter Templates (NEW):**
- Click **"Apply Template"** to populate standard fields for common conditions
- Available templates: Hypertension Follow-up, Diabetes Review, Post-Op Checkup, etc.
- Saves time for routine visits

**Tips:**
- Encounters are "ongoing" until you close them
- You can re-open closed encounters to amend (creates audit trail)
- Only you (and super admin) can edit your encounters
- All encounter data is part of patient's permanent record

---

#### 3. Order Lab Tests

**Scenario:** Patient needs blood work to monitor kidney function.

**Steps:**
1. In open encounter, scroll to **"Lab Orders"** section
2. Click **"+ Order Lab"** button
3. Select test type:
   - Search by name: "Full Blood Count", "Renal Panel", etc.
   - OR scroll list: Hematology, Chemistry, Immunology, etc.
4. Fill test details:
   - **Priority:** Routine / Urgent
   - **Clinical Indication:** Why you're ordering (e.g., "Monitor BP control")
   - **Fasting Required?** Yes / No
   - **Special Instructions:** (e.g., "Collect at 8 AM before breakfast")
5. Click **"Order"**
6. Lab receives order immediately
7. You'll see **"Pending"** status
8. When completed, results appear in green: **"Completed"**

**Results Viewing:**
- Results appear in "Lab Results" section of patient record
- **Green** = Normal range
- **Yellow** = Borderline
- **Red** = Abnormal (may need action)
- Abnormal results trigger clinical alert (notification icon)

**Tips:**
- Lab tech can see your orders in their "Lab Worklist"
- Provide clear clinical indication so lab tech knows urgency
- Check results daily if urgent order

---

#### 4. Write Prescriptions

**Scenario:** Hypertensive patient needs medication adjustment.

**Steps:**
1. In open encounter, scroll to **"Prescriptions"** section
2. Click **"+ New Prescription"** button
3. Fill prescription details:
   - **Drug Name:** Start typing, autocomplete appears (e.g., "Lisinopril")
   - **Dose:** 10 (number)
   - **Dose Unit:** mg / tablets / mL (dropdown)
   - **Frequency:** Once daily / Twice daily / Every 8 hours (dropdown)
   - **Route:** Oral / IV / Intramuscular (dropdown)
   - **Duration:** 30 (number)
   - **Duration Unit:** Days / Weeks / Months
   - **Quantity:** Number of pills/bottles to dispense
   - **Refills:** How many times patient can refill (0-5)
   - **Indication:** Why you're prescribing (e.g., "Hypertension management")
   - **Notes:** Special instructions (e.g., "Take with food if nausea")
4. System checks for **drug interactions** automatically
5. If interaction detected:
   - Yellow alert: "Minor interaction" — can proceed
   - Red alert: "Severe interaction" — must address or add note
6. Review patient **allergies** at top of screen (red banner if allergic)
7. Click **"Save Prescription"**

**Prescription Status Flow:**
- **Active:** Just prescribed, awaiting pharmacy
- **Dispensed:** Pharmacy handed over to patient
- **Administered:** Nurse gave to patient (for hospitalized patients)
- **Completed:** Full course done

**Refill Prescriptions:**
- In past prescriptions section, click **"Refill"** on medication patient wants more of
- Automatically fills same details; you can adjust
- System prevents refills beyond 5x for controlled drugs

**Tips:**
- If drug not in autocomplete, type full name and hit Enter
- Pharmacy sees all pending prescriptions in "Pharmacy Worklist"
- Patient gets SMS when prescription ready for pickup
- Verify allergy list before prescribing

---

#### 5. AI Clinical Decision Support

**Scenario:** Complex patient. Want AI to analyze risk and suggest investigations.

**Steps:**
1. Open patient record
2. Scroll to **"AI Analysis"** card (if enabled at your hospital)
3. AI status shows: ✅ **"AI Enabled"** or ⚠️ **"AI Disabled at your hospital"**
4. If enabled, click **"Analyze Patient"** button
5. Wait 30-60 seconds while AI processes patient data
6. Results appear in expandable sections:

   **Overall Risk Score:** (0-100)
   - 0-30 = Low risk
   - 30-70 = Moderate risk
   - 70+ = High risk ⚠️

   **Risk Factors:** List of things elevating score with explanation
   - Example: "Hypertension (uncontrolled): BP readings 145-160 despite meds"

   **Key Findings:** Current health status summary
   - Example: "Blood pressure suboptimal. Lipid panel pending."

   **AI Recommendations:** Suggested next steps
   - Example: "Consider increasing lisinopril dose or adding amlodipine" (Confidence: 85%)
   - Example: "Order lipid panel if not done in last 6 months"

   **Contraindications:** Things to avoid with this patient
   - Example: "Avoid NSAIDs - patient has chronic kidney disease"

7. **Use AI to inform your decision**, not replace it
8. Click **"Accept"** to log you reviewed recommendations
9. Click **"Dismiss"** if you disagree (creates audit trail)

**AI Confidence Scores:**
- 90%+ = High confidence, strongly recommend
- 70-90% = Moderate confidence, consider if fits your plan
- < 70% = Low confidence, use caution or seek second opinion

**When NOT to Trust AI:**
- Recent diagnosis not yet in system (AI catches up after 24 hours)
- Rare conditions (AI trained on common cases)
- Patient with unusual presentation
- Always consult senior colleague if unsure

**Tips:**
- AI analyzes last 30 days of data by default
- AI sees allergies and contraindications
- AI recommendations logged in audit trail
- AI is NOT real-time diagnosis; always examine patient

---

#### 6. Diagnoses (ICD-10 Coding)

**Scenario:** Patient diagnosed with hypertension. Need to document with code.

**Steps:**
1. In open encounter, scroll to **"Diagnoses"** section
2. Click **"+ Add Diagnosis"** button
3. Search for condition:
   - Type "hypertension" in search box
   - Autocomplete shows ICD-10 codes:
     - I10 = Essential hypertension
     - I11 = Hypertensive heart disease
     - I15 = Secondary hypertension
4. Click correct code (e.g., I10)
5. Fill details:
   - **Status:** Active / Resolved / Suspected
   - **Date Diagnosed:** (auto-filled as today, can change)
   - **Notes:** Additional context (optional)
6. Click **"Save"**

**Diagnosis Status:**
- **Active:** Ongoing condition, patient currently has it
- **Resolved:** Patient recovered or condition resolved
- **Suspected:** Awaiting confirmation (e.g., suspected TB pending culture)

**Tips:**
- Use ICD-10 codes for billing and statistics (mandatory in most systems)
- Multiple diagnoses OK for complex patients
- Diagnoses are part of patient's permanent record
- Can't delete diagnoses; can only mark as resolved

---

#### 7. Referrals to Other Hospitals

**Scenario:** Your hospital doesn't have cardiothoracic surgery. Need to refer patient.

**Steps:**
1. In patient record, click **"Create Referral"** button
2. Fill referral details:
   - **Receiving Hospital:** Select from dropdown (other hospitals in network)
   - **Specialty:** Cardiothoracic Surgery / Oncology / etc.
   - **Urgency:** Routine / Urgent / Emergency
   - **Chief Complaint:** What's the main issue (e.g., "Severe aortic stenosis")
   - **Clinical Summary:** 2-3 sentence summary of patient status and why referral needed
   - **Recommended Service:** What you think patient needs
   - **Expected Arrival:** When patient will arrive (if known)
3. Click **"Send Referral"**
4. Receiving hospital gets notification
5. Referral status shows: **"Pending"** (awaiting acceptance)
6. When accepted: **"Accepted"** ✅
7. When patient seen: **"Completed"** ✓

**Referral Status Tracking:**
- View in "Referrals" section of patient record
- Receiving doctor can message back with acceptance notes
- Creates care continuity across hospitals

**Tips:**
- Include as much clinical detail as possible for receiving doctor
- Receiving hospital gets access to your clinical notes (with consent)
- Follow-up with receiving doctor after transfer
- If urgent, consider calling receiving hospital directly

---

#### 8. Cross-Facility Records & Consent

**Scenario:** Patient was treated at another hospital. Want to see their records.

**Steps:**
1. Search patient (searches across all hospitals if consented)
2. In patient record, look for **"Cross-Facility Access"** section
3. If another hospital's records available:
   - Shows: "Korle-Bu Teaching Hospital: Records available"
   - **Scope:** SUMMARY (demographics only) or FULL_RECORD (all clinical data)
4. Click **"View Cross-Facility Records"** to see available data
5. Records shown with source hospital and date

**If No Access:**
- Shows: "Ridge Regional Hospital: No consent granted"
- Option to **"Request Consent"** from that hospital
- That hospital's admin reviews and approves within 1-2 business days

**Tips:**
- Consent helps patient get better care (all hospitals can see full history)
- You can request consent anytime during patient encounter
- Consent has expiration date (usually 90 days)
- Both hospitals can revoke consent anytime

---

#### 9. Break-Glass Emergency Access

**Scenario:** Unconscious patient arrives. No consent from other hospital. Need records NOW.

**Steps:**
1. Patient record shows: ⚠️ **"No Consent - Emergency Access Available"**
2. Click **"Break-Glass Access"** button (red emergency button)
3. System asks: **"Why do you need access?"**
   - Select: Emergency Treatment / Allergy Check / Critical Decision
   - Add notes: "Patient unconscious, no family present"
4. Click **"Confirm Access"**
5. Records unlock for **15 minutes only**
6. View all available data from other hospitals
7. After 15 minutes: access automatically expires
8. **Audit log recorded:** Who accessed, when, reason, for how long

**Important:**
- ⚠️ Break-glass is **audited closely** — misuse reported to management
- Only use in true emergencies (patient care immediately threatened)
- Takes ~2 seconds to grant; stays active for exactly 15 minutes
- Documented in compliance reports for governance

**Tips:**
- Don't use break-glass for convenience (consents are faster)
- Always document clinical reason
- After emergency passes, request formal consent if ongoing care
- Supervisors notified of break-glass use

---

### Troubleshooting

**"Can't find patient in search"**
- Check spelling (system doesn't do fuzzy matching for privacy)
- Try searching by Ghana Health ID instead of name
- Patient may not be registered yet at your hospital
- Try searching by phone number

**"Error: 403 Forbidden when viewing patient"**
- Patient's hospital differs from your hospital
- Request cross-facility consent (button in patient record)
- Use break-glass if true emergency

**"Can't close encounter - 'Incomplete records' error"**
- Check all required sections are filled:
  - Chief complaint
  - At least one finding or vital sign
  - Assessment or diagnosis
- Add missing data and try again

**"Drug interaction alert blocking prescription"**
- Read the alert: what's the interaction?
- If minor (yellow): can proceed, but inform patient
- If severe (red): choose different drug or add clinical note explaining why benefit > risk
- Consult pharmacist if unsure

**"Referral not sending to other hospital"**
- Check receiving hospital is selected
- Check your internet connection
- Try again, or contact IT if persists

---

### Common Workflows

#### Hypertension Follow-Up (15 min)

1. **Search patient** → Open record
2. **Create new encounter** → Chief complaint: "Hypertension follow-up"
3. **Record vitals** → BP, pulse, weight
4. **Add diagnosis** → I10 (Essential hypertension), Status: Active
5. **Review last labs** → Click "Labs" tab
6. **Order new labs** → Lipid panel if last one > 6 months ago
7. **Adjust prescription** → If BP not at goal, increase medication
8. **AI analysis** (optional) → Get recommendations for optimization
9. **Set follow-up** → "Return in 1 month"
10. **Close encounter** → Click "Close Encounter" button

#### Emergency Triage (5 min)

1. **Patient checks in** → Receptionist creates walk-in record
2. **Quick vitals** → Nurse records BP, pulse, O2 sat
3. **Triage color** → Assign Red/Yellow/Green based on ESI protocol
4. **Assign doctor** → Route to appropriate specialist
5. **Open encounter** → Start clinical notes
6. **Order urgent tests** → Labs, X-ray, EKG as needed
7. **Monitor in real-time** → ED queue shows your patient's status

---

---

## Nurse

### Overview

As a nurse, you'll use MedSync to:
- **Manage ward patients** and see all admitted patients
- **Record vital signs** (BP, temperature, O2, etc.) for multiple patients
- **Administer medications** using Medication Administration Record (MAR)
- **Document nursing notes** during shifts
- **Alert doctors to critical vitals** (automatic escalation)
- **Manage shift handover** to next shift
- **Track pending tasks** (meds due, vitals overdue, etc.)
- **Receive clinical alerts** for patients needing attention

### Key Features

#### 1. Ward Dashboard

**Scenario:** Start of shift. You're assigned to Cardiology Ward. Need to see all patients.

**Steps:**
1. Log in → MedSync dashboard loads
2. See banner: **"Operating in: Cardiology Ward"** (shows your assigned ward)
3. Click **"Ward Dashboard"** in sidebar
4. Dashboard shows:
   - **Census:** 15 patients admitted (5 high-risk)
   - **Patient list:** Each patient card showing:
     - Bed number: A-102
     - Patient name: Kwame Owusu
     - Admission reason: Post-op cardiac
     - Status: ✅ Stable / ⚠️ Alert / 🔴 Critical
     - Last vitals: BP 120/80 (2 hours ago)
     - Next med due: Lisinopril 10mg (in 30 min)
5. Click patient card to open full record
6. All vitals, meds, alerts visible in one view

**Ward Occupancy View:**
- Shows all 20 beds in your ward
- Green = Available
- Blue = Occupied (patient name)
- Yellow = Needs cleaning
- Red = Critical patient alert

**Tips:**
- Dashboard refreshes every 2 minutes automatically
- Alerts show as red dots on patient cards
- Click alert icon to see what's flagged

---

#### 2. Vital Signs Recording

**Scenario:** 08:00 AM. 15 patients need vitals recorded. Do them all efficiently.

**Steps:**

**Record Vitals (One Patient):**
1. Open patient record
2. Click **"+ Record Vitals"** button
3. Enter measurements:
   - Temperature: 37.2 °C
   - Systolic BP: 120 mmHg
   - Diastolic BP: 80 mmHg
   - Heart Rate: 72 bpm
   - Respiratory Rate: 16 breaths/min
   - Oxygen Saturation: 98.5 %
   - Blood Glucose: 95 mg/dL (if diabetic)
4. Click **"Save"**
5. System auto-checks ranges:
   - ✅ Green = Normal
   - ⚠️ Yellow = Borderline (e.g., BP 140/90)
   - 🔴 Red = Abnormal (e.g., O2 sat 88%)
6. If red, system auto-alerts doctor

**Record Vitals (Batch - Multiple Patients):**
1. Click **"Record Vitals in Batch"** button
2. Select patients to record vitals for (checkboxes)
3. For each patient, fill vitals in order (system moves down)
4. Type values quickly (tab to next field)
5. Click **"Save All"** at bottom
6. All vitals saved in seconds

**Vital Alerts:**
- **Systolic BP > 160 or < 90** → Alert doctor
- **Heart rate > 120 or < 50** → Alert doctor
- **O2 saturation < 94%** → Alert doctor immediately
- **Temperature > 38.5°C** → Alert doctor
- **Respiratory rate > 30 or < 10** → Alert doctor immediately

**Tips:**
- Batch entry saves 10 minutes vs one-by-one
- Always record at same time each day (8am, 2pm, 8pm) if possible
- System keeps history; can see trends over time
- Abnormal vitals trigger alerts to doctors automatically

---

#### 3. Medication Administration Record (MAR)

**Scenario:** 08:00 medication time. Multiple patients need meds.

**Steps:**

**View Medications Due:**
1. Click **"Medication Schedule"** in sidebar
2. System shows: **"12 medications due in next 2 hours"**
3. List sorted by bed number:
   - Bed A-102: Kwame Owusu - Lisinopril 10mg - Due now ⏰
   - Bed A-105: Ama Mensah - Amoxicillin 500mg - Due in 30 min
   - Etc.

**Administer Medication:**
1. Click medication in list
2. System opens: **"Medication Administration Record"**
3. Shows:
   - Patient name & bed number
   - Drug: Lisinopril 10mg
   - Dose: 10mg
   - Route: Oral
   - Frequency: Once daily
   - Prescribed by: Dr. Kwame Adjei
4. Verify:
   - ✅ Check patient ID band matches
   - ✅ Check allergy list (red banner if allergic)
   - ✅ Check drug name & dose on label
5. Ask patient: **"Do you have any new allergies?"**
6. If all checks pass, click **"Administer"** button
7. Fill:
   - Time administered: 08:05 (auto-fills current time)
   - Notes: (optional, e.g., "Patient took with breakfast")
8. Click **"Confirm Administered"**
9. Medication marked ✅ **"Administered"** (green checkbox)

**If Medication Refused:**
1. Click **"Hold / Skip"** button
2. Reason: Select from dropdown
   - Patient refused
   - Patient nauseous
   - Unable to take orally (NPO)
   - Other
3. Add notes: (e.g., "Patient nauseous, will try again at noon")
4. Click **"Save"**
5. Medication marked ⏸️ **"Held"** (yellow flag)
6. Doctor notified to assess need to reschedule

**Tips:**
- Always verify 5 "Rights": Right Patient, Right Drug, Right Dose, Right Route, Right Time
- Document administration immediately (don't do end-of-shift documentation)
- If medication not available, click "Out of Stock" and alert doctor
- Check interactions with recently ordered new meds

---

#### 4. Nursing Notes

**Scenario:** Patient Kwame Owusu had difficult night. Document nursing assessment.

**Steps:**
1. Open patient record
2. Click **"+ New Nursing Note"** button
3. Select note type:
   - Shift note (default)
   - Symptom assessment
   - Patient education
   - Incident report
4. Write note (free text):
   - **Good format:** "Patient alert and oriented. Pain controlled on current meds (7/10 → 4/10). Sleeping well. Eating regular diet. No N/V. Ambulating with assistance. Dressing clean and dry, no signs of infection. Supportive and engaged with treatment plan."
   - **Avoid:** Abbreviations that aren't standard; emotional language; unverified information
5. Click **"Save"**
6. Note timestamped and linked to patient record
7. Doctor can see in patient record

**Clinical Alert Escalation:**
- If note mentions concerning finding, use **"Alert Doctor"** button
- Example findings that should alert:
  - Difficulty breathing
  - Chest pain
  - Altered mental status
  - Uncontrolled pain
  - Fever > 38.5°C
  - Vomiting/diarrhea
  - Rash or swelling

**Tips:**
- Nursing notes are legal documentation (may be used in court)
- Never document something you didn't personally observe
- Focus on objective findings, not subjective opinions
- If serious issue, don't wait for documentation—call doctor directly

---

#### 5. Shift Handover

**Scenario:** Your 8-hour shift ending at 20:00. Next nurse (Ama) taking over.

**Steps:**

**Before Shift Ends:**
1. Click **"End Shift"** button
2. System asks: **"Write handover notes for next shift"**
3. Document:
   - **Critical patients:** (e.g., "Bed A-102: Post-op cardiac, stable, BP well-controlled, pain minimal")
   - **Pending tasks:** (e.g., "Awaiting lab results for patient in A-105—check at 21:00")
   - **Medication issues:** (e.g., "Patient A-110 nauseous, held am meds")
   - **Alerts:** (e.g., "A-115 has new allergy to Penicillin")
   - **Positive notes:** (e.g., "Excellent day—all patients stable, no incidents")
4. List patients handed over to (e.g., Ama Mensah)
5. Click **"Submit Handover"**
6. Status: **"Pending Acknowledgment"** ⏳

**Next Shift Acknowledgment:**
1. Incoming nurse (Ama) logs in
2. System shows: **"Handover from Akosua waiting for acknowledgment"**
3. Ama reads handover notes
4. Ama clicks **"I Acknowledge"** button
5. Fills:
   - **Confirmation:** "I have reviewed all information. I am ready to take over."
   - Optional: Add questions or clarifications
6. Click **"Acknowledge"**
7. Handover marked ✅ **"Acknowledged"** (green)
8. Both you and Ama have record of transfer of care

**In-Person Handover Tips:**
- Hand over notes 15 minutes before shift ends
- Walk through each patient with incoming nurse
- Point out any equipment issues or missing supplies
- Answer questions on the spot
- Both sign off in system once complete

**Tips:**
- Handover creates legal record of care transition
- Prevents information loss or repeated assessments
- New nurse knows what happened during previous shift
- If issue during handover, document it

---

#### 6. Critical Alerts

**Scenario:** Patient Kwame's BP suddenly drops to 90/55. System alerts you immediately.

**What Happens:**
1. **Phone notification:** Buzzes with alert
2. **Dashboard:** Patient card turns 🔴 RED
3. **Banner at top:** "⚠️ CRITICAL ALERT: Kwame Owusu - Vital Signs Abnormal"
4. Click alert → Opens patient record
5. See which vital is abnormal: **BP 90/55** (red)

**Your Response:**
1. **Go directly to patient** (within 2 minutes)
2. **Reassess vitals:**
   - Re-check BP manually (machine may malfunction)
   - Check consciousness, skin color, breathing
   - Ask: "How do you feel? Any dizziness? Pain?"
3. **If still abnormal:**
   - Press **"Alert Doctor"** button (big red button)
   - Doctor paged immediately
   - Stay with patient until doctor arrives
4. **If normal (was sensor error):**
   - Click **"Dismiss Alert"** (yellow button)
   - Re-check in 15 minutes

**Critical Vital Thresholds:**
- **BP:** < 90 systolic OR > 180 systolic
- **Heart Rate:** < 50 OR > 120
- **O2 Saturation:** < 94%
- **Temperature:** > 39°C
- **Respiratory Rate:** < 10 OR > 30

**Tips:**
- Critical alerts are prioritized over regular messages
- Don't ignore alerts; always respond within 2 minutes
- False alarms OK; reassess to confirm

---

### Troubleshooting

**"Medication not showing in schedule"**
- Doctor may not have confirmed order yet
- Wait 5 minutes for system to sync
- Or ask doctor to check pending prescriptions

**"Can't administer medication - 'Allergy warning'"**
- Check allergy list at top of screen
- If allergy is documented incorrectly, mark it inactive
- If patient says it's new allergy, add it immediately
- Alert doctor before administering

**"Vital sign alert won't dismiss"**
- Alert only clears if you update vital or confirm resolution
- Don't dismiss if patient still symptomatic
- Alert doctor if concerned

**"Handover didn't send"**
- Check internet connection
- Try again
- Contact IT if error persists

---

### Common Workflows

#### Routine Shift Start (30 min)

1. **Log in** → See ward dashboard
2. **Review all patients** → Click each card, read notes
3. **Check alerts** → See if any critical flags
4. **Read handover** → From previous shift
5. **Record morning vitals** → Use batch entry (15 min)
6. **Administer morning meds** → Check MAR (10 min)
7. **Alert doctor** → Any concerns noted by previous shift

#### Medication Round (45 min)

1. **Check medication schedule** → Sort by time due
2. **Per patient:** Take vitals (if needed), verify allergy, give med, document
3. **If refused/held:** Document reason
4. **If alert:** Alert doctor immediately
5. **Recheck in 30 min:** Any side effects?

---

---

## Lab Technician

### Overview

As a lab tech, you'll use MedSync to:
- **Receive lab orders** from doctors
- **View worklist** of tests to run
- **Enter lab results** and reference ranges
- **Flag abnormal results** for doctor review
- **Bulk submit multiple results** after batch testing
- **View quality metrics** (turnaround time, error rate)

### Key Features

#### 1. Lab Worklist

**Scenario:** Start of day. Check all lab orders waiting.

**Steps:**
1. Log in → Click **"Lab Worklist"** in sidebar
2. See list of all pending tests:
   - Patient: Kwame Owusu
   - Test: Full Blood Count (CBC)
   - Priority: Routine
   - Ordered by: Dr. Kwame Adjei
   - Ordered at: 14:30 yesterday
   - Status: Pending (waiting for you to process)
3. Sorted by priority:
   - 🔴 **Urgent** (3 tests) — Start with these
   - 🟡 **Routine** (25 tests) — Most common
   - ⚪ **Scheduled** (5 tests) — Can batch later
4. Click test to open details
5. Shows:
   - Patient info & location
   - Clinical indication (why doctor ordered)
   - Special instructions (e.g., "Fasting", "Collect early AM")
   - Target delivery time

**Tips:**
- Process urgent tests within 1 hour
- Batch routine tests together (more efficient)
- Note special instructions before collecting sample

---

#### 2. Enter Lab Results

**Scenario:** Completed CBC on patient Kwame. Enter results.

**Steps:**
1. From worklist, click test or open test details
2. Click **"Enter Results"** button
3. Form appears with test parameters:
   - **Hemoglobin:** _____ g/dL
   - **Hematocrit:** _____ %
   - **WBC:** _____ K/uL
   - **Platelets:** _____ K/uL
   - Etc.
4. Enter measured values:
   - Hemoglobin: 13.5
   - Hematocrit: 41
   - WBC: 7.2
   - Platelets: 250
5. System auto-compares to reference ranges:
   - Hemoglobin 13.5 g/dL → ✅ Normal (ref: 13.5-17.5 for males)
   - WBC 7.2 K/uL → ✅ Normal (ref: 4.5-11)
   - Etc.
6. Add notes if needed (optional):
   - "Sample hemolyzed but still usable"
   - "Retested due to initial machine error"
7. Click **"Save & Submit"**
8. Results locked (can't edit without amendment)
9. Doctor notified of results immediately

**Result Flags:**
- **Normal** → ✅ Green
- **Borderline** → ⚠️ Yellow (e.g., slightly low hemoglobin)
- **Abnormal** → 🔴 Red (e.g., very high WBC)
- **Critical** → 🔴 RED + Doctor paged immediately (e.g., hemoglobin < 7)

**Tips:**
- Double-check values before submitting
- Critical results need verbal confirmation to doctor (don't rely on system only)
- System calculates derived values (e.g., MCV from hemoglobin/hematocrit)

---

#### 3. Bulk Submit Results

**Scenario:** Processed 20 CBCs at once. Enter all results quickly.

**Steps:**
1. Click **"Bulk Result Entry"** button in Lab section
2. System shows table: Patient | Test | Result1 | Result2 | etc.
3. Rows pre-populated from completed tests
4. Enter values row by row:
   - Tab between cells (faster than clicking)
   - Example: 13.5 [TAB] 41 [TAB] 7.2 [TAB] 250 [ENTER]
5. Continue for all 20 patients
6. Click **"Validate All"** — System checks for errors
7. If errors (e.g., value < 0, missing required field):
   - System highlights in red
   - Fix error
   - Re-validate
8. Click **"Submit All"** when all valid
9. All 20 results saved at once ✅

**Efficiency Gains:**
- Batch entry: 20 tests in 15 minutes
- One-by-one: 20 tests in 45 minutes
- Saves 30 minutes/day with 60+ tests

**Tips:**
- Use batch for high-volume routine tests
- Review ranges before batch entry to catch outliers

---

#### 4. Quality Metrics & Analytics

**Scenario:** Monthly review. Check lab performance.

**Steps:**
1. Click **"Lab Analytics"** in sidebar
2. Dashboard shows:
   - **Turnaround Time:** Avg 2.5 hours (target < 2 hours for routine)
   - **Error Rate:** 0.2% (target < 1%)
   - **Sample Rejection:** 1.1% (target < 2%)
   - **Critical Result Reporting:** 100% (target 100%)
3. Trends over time:
   - Graph: Turnaround time last 30 days (should be flat)
   - Graph: Tests per day (volume trend)
   - Graph: Most common tests (CBC, Urinalysis, Blood Glucose)

**Performance Targets:**
- Routine tests: < 2 hours
- Urgent tests: < 30 minutes
- Critical results: Phone to doctor within 5 minutes
- Sample rejection: < 2%

**Improvements:**
- If turnaround > 2 hours: optimize batch size or add staff
- If errors rising: review procedures, add training
- If rejection rising: check sample collection technique

**Tips:**
- Track metrics weekly, not just monthly
- Discuss trends with team
- Celebrate when targets met

---

### Troubleshooting

**"Can't find test in worklist"**
- Test may not be ordered yet by doctor
- Refresh page or wait 5 minutes for sync
- Search for patient name and check orders

**"Result rejected - 'Out of range'"**
- System detected value outside possible range (e.g., hemoglobin 500)
- Check instrument reading for typo
- Re-enter correct value

**"Doctor didn't receive critical result alert"**
- Call doctor directly (don't rely on system only)
- Check doctor's phone is registered for alerts
- Critical results should ALWAYS be phoned, not just emailed

---

### Common Workflows

#### Morning Shift (4 hours)

1. **Check worklist** → Prioritize urgent (10 min)
2. **Process urgent tests** → 3 tests (30 min)
3. **Batch routine tests** → 20 CBC + 10 urinalysis (90 min)
4. **Bulk submit results** (15 min)
5. **Document quality issues** → Any rejections or errors (10 min)

---

---

## Receptionist

### Overview

As a receptionist, you'll use MedSync to:
- **Register new patients** or check existing patients in
- **Manage appointments** (schedule, cancel, reschedule)
- **Create walk-in records** for unscheduled patients
- **Check appointment availability** for doctors
- **Print patient labels/forms**
- **View waiting queue** (for triage areas)

### Key Features

#### 1. Patient Check-In

**Scenario:** Patient Kwame Owusu arrives for appointment. Check him in.

**Steps:**
1. **Search patient:**
   - Type name: "Kwame" → System finds "Kwame Owusu"
   - Or scan patient ID card barcode (auto-fills name)
2. **Verify:**
   - "Is this you? Kwame Owusu, DOB: 1990-05-15?" (shows photo if available)
   - Patient says yes
3. **Click "Check In"** button
4. System updates:
   - Appointment status: ✅ **"Checked In"** (green)
   - Waiting area notified: Patient now in queue
   - Doctor notified: Patient ready to be seen
5. **Print forms** (if needed):
   - Click "Print Intake Form" → Prints form for patient to update address/insurance
   - Click "Print Wristband" → Thermal printer labels with patient ID

**Appointment Status Flow:**
- **Scheduled** (blue) → Patient hasn't arrived
- **Checked In** (green) → Patient in waiting area
- **With Doctor** (orange) → Doctor seeing patient
- **Completed** (gray) → Visit done
- **No-Show** (red) → Patient didn't arrive

**Tips:**
- Check in within 5 minutes of appointment time
- If patient late, wait 15 minutes before marking no-show
- For walk-ins, create new appointment record

---

#### 2. Schedule New Appointment

**Scenario:** Patient wants follow-up appointment in 1 month. Book it.

**Steps:**
1. **Search patient** or have them open medical record
2. Click **"+ New Appointment"** button
3. Fill appointment details:
   - **Doctor:** Select from dropdown (shows available doctors)
   - **Department:** Auto-filled based on doctor's specialty
   - **Date & Time:** Click calendar, select date, then time slot
   - **Appointment Type:** Follow-up / New complaint / Procedure
   - **Duration:** Usually 30 min (auto-filled by doctor preference)
   - **Notes:** (optional) "Hypertension follow-up, check if BP controlled"
4. System shows **Doctor Availability:**
   - Green = Available
   - Red = Booked
   - Gray = Outside clinic hours
5. Select time slot
6. Click **"Book Appointment"**
7. Confirmation:
   - Appointment saved ✅
   - Confirmation number shown (e.g., "APT-20250120-001")
   - Option to print appointment card
8. **Send reminder** (automatic):
   - SMS sent 24 hours before appointment
   - SMS sent 1 hour before appointment

**Rescheduling:**
- Patient calls to reschedule
- Click "Reschedule" on existing appointment
- Select new date/time
- Old appointment cancelled, new one created
- Patient gets SMS of new time

**Cancellation:**
- Click "Cancel" on appointment
- Reason: Select from dropdown (e.g., "Patient request", "Doctor emergency")
- Slot freed up for other patients
- Patient gets cancellation SMS

**Tips:**
- Always provide confirmation number to patient
- Print appointment card with date/time/doctor name
- Ask patient if they prefer AM or PM
- For elderly patients, offer 2-3 time options

---

#### 3. Doctor Availability Check

**Scenario:** Patient asks "When can I see the cardiologist?" Check availability.

**Steps:**
1. Click **"Check Doctor Availability"** button
2. Select doctor: "Dr. Kwame Adjei" (Cardiology)
3. Calendar opens showing next 2 weeks
4. Green = Available slots
5. **Next available:** Friday 14:00, Saturday 09:30, etc.
6. Offer to book
7. System automatically avoids:
   - Doctor's off days
   - Lunch break
   - Already booked slots
   - Operating room time

**Tips:**
- Show patient 3 options if possible
- If very full, offer to put on waitlist
- Waitlist automatically contacts patient if cancellation

---

#### 4. Walk-In Registration

**Scenario:** Patient arrives without appointment. Create walk-in record.

**Steps:**
1. **Check if patient in system:**
   - Search by name/phone
   - If not found: Register new patient (see Doctor section)
2. **Create Walk-In Record:**
   - Click **"Create Walk-In"** button
   - Select: Department / Chief Complaint (e.g., "Acute fever")
   - Click **"Check In"**
3. System shows:
   - Queue position: **"You are #3 in queue"**
   - Estimated wait: **"45 minutes"**
   - Instructions: "Please wait in triage area"
4. **Call for triage:**
   - Nurse called, assigns triage color (Red/Yellow/Green)
   - Routing: Patient sent to appropriate treatment area

**Walk-In Queue Management:**
- View "Walk-In Queue" in sidebar
- Shows all waiting patients
- Sort by: Time arrived, priority, department
- Track queue length and average wait time

**Tips:**
- Walk-ins may wait 1-3 hours depending on volume
- Always offer to schedule future appointments instead
- Mark patients seen in real-time to keep queue accurate

---

#### 5. Appointment Bulk Import

**Scenario:** Doctor provides Excel list of 50 follow-ups to schedule. Bulk import instead of manual entry.

**Steps:**
1. Get appointments Excel file from doctor
2. Format:
   ```
   Patient Name | Date | Time | Doctor | Notes
   Kwame Owusu  | 2025-01-20 | 14:00 | Dr. Kwame | HTN F/U
   Ama Mensah   | 2025-01-20 | 15:00 | Dr. Kwame | DM F/U
   ```
3. Click **"Bulk Import Appointments"** button
4. Upload Excel file
5. System processes:
   - Validates patient names (finds in system)
   - Checks doctor availability
   - Checks for duplicate appointments
   - Shows preview: "50 appointments ready to import"
6. Click **"Import"**
7. All 50 created in 30 seconds ✅
8. Patients automatically SMS'd with appointments

**Validation:**
- If patient not found: Shows error, skip that row
- If time slot taken: Shows warning, can retry or pick different time
- Fix errors in Excel and re-upload

**Tips:**
- Bulk import saves hours vs manual entry
- Always validate file before uploading
- Patients notified automatically via SMS

---

#### 6. Print Patient Materials

**Steps:**
1. Open patient record
2. Click **"Print"** menu:
   - **Appointment Card:** Date, time, doctor, clinic location
   - **Patient Wristband:** Barcode + patient ID (for hospital admission)
   - **Intake Form:** Address, insurance, emergency contact (for patient to update)
   - **Medication List:** Current prescriptions (for patient reference)
   - **Lab Requisition:** For lab tests (if doctor ordered)
3. Select printer destination
4. Click "Print"
5. Materials ready in 30 seconds

**Tips:**
- Print appointment card at booking
- Wristband printed at check-in
- Intake form printed for new patients
- Lab forms printed when doctor orders test

---

### Troubleshooting

**"Can't find patient in system"**
- Check spelling
- Search by phone number instead
- Patient may not be registered; offer to register now
- May be from another hospital (search "Cross-Hospital Patients")

**"Doctor showing as unavailable, but patient says he's here"**
- Doctor may have marked himself busy for lunch
- Or in OR for procedure
- Check doctor's calendar
- If truly available, contact doctor directly

**"Appointment time shows available but won't book"**
- May have just been booked by someone else
- Refresh page and try again
- Or select different time

**"Can't send SMS to patient"**
- Check phone number is correct (starts with +233 or 05)
- SMS service may be down; try again later
- Patient may have opted out of SMS

---

### Common Workflows

#### Registration & Check-In (5 min)

1. **Greet patient** → Smile, ask name
2. **Search in system** → Find or register if new
3. **Verify demographics** → "Is address 123 Main St still correct?"
4. **Update insurance** → If changed
5. **Check in** → Click check-in button
6. **Print wristband** → Scan to confirm
7. **Direct to area** → "Doctor will see you in Clinic A"

#### Busy Clinic (high volume)

1. **Pre-registration:** Have patients fill forms online before arrival
2. **Batch check-in:** Multiple patients at once during rush
3. **Waitlist:** If full, offer to put on waitlist with SMS callback
4. **Walk-in triage:** Prioritize urgent over routine

---

---

## Hospital Administrator

### Overview

As a hospital admin, you'll use MedSync to:
- **Manage staff** (hire, onboard, roles, permissions)
- **Manage wards & beds** (create, assign, track occupancy)
- **View audit logs** (who did what, compliance)
- **Access analytics** (patient volume, appointments, AI usage)
- **Manage billing** (invoices, NHIS claims)
- **Oversee cross-facility access** (consents, referrals)
- **Create and manage departments** (labs, wards, specialties)

### Key Features

#### 1. User Management (Hiring & Onboarding)

**Scenario:** Hire new doctor. Get them onboarded in 1 hour.

**Steps:**

**Step 1: Create User Invite**
1. Click **"Staff Management"** → **"Invite New User"**
2. Fill details:
   - **Email:** newdoctor@medsync.gh
   - **Full Name:** Dr. Ama Kusi
   - **Role:** Doctor (dropdown)
   - **Ward Assignment:** Cardiology Ward (if applicable)
   - **Phone:** +233501234567
3. Click **"Send Invitation"**
4. Doctor receives email with activation link
5. Link valid for 7 days

**Step 2: Doctor Activates Account**
1. Doctor clicks link in email
2. Creates password (12+ chars, uppercase, lowercase, digit, symbol)
3. Sets up TOTP (scan QR code with authenticator app)
4. Account now ✅ **Active**

**Step 3: Assign MFA & Permissions**
1. Back in admin dashboard, search doctor's name
2. Confirm MFA enabled ✅
3. Verify role correct: Doctor ✅
4. Verify ward assignment: Cardiology ✅
5. Doctor can now log in and start work

**Bulk Invite:**
1. Click **"Bulk Invite Staff"**
2. Upload CSV:
   ```
   email,full_name,role,ward
   doctor1@hospital.gh,Dr. One,doctor,cardiology
   nurse1@hospital.gh,Nurse One,nurse,cardiology
   ```
3. Click "Import"
4. All 2 staff invited at once
5. Get 3 bulk reminder emails over week to activate

**Tips:**
- Don't share activation link via SMS (security)
- New doctor cannot access patient data until activated
- Role assignment restricts what features they see
- Ward assignment (for nurses/staff) limits patient access

---

#### 2. Ward & Bed Management

**Scenario:** Open new Cardiology Ward. Add 20 beds and assign staff.

**Steps:**

**Create Ward:**
1. Click **"Ward Management"** → **"Create Ward"**
2. Fill:
   - **Ward Name:** Cardiology Ward
   - **Department:** Internal Medicine
   - **Total Beds:** 20
   - **Ward Manager:** Nurse Ama Kwarteng (dropdown)
   - **Description:** "24-bed cardiac care ward with ICU capabilities"
3. Click **"Create"**
4. Ward now appears in sidebar for staff assignment

**Add Beds:**
1. Click ward name → **"Manage Beds"**
2. Click **"Add Beds in Bulk"**
3. Fill:
   - **Number of Beds:** 20
   - **Bed Prefix:** A (beds will be A-100, A-101, etc.)
   - **Starting Number:** 100
   - **Bed Type:** Standard / ICU / Isolation
4. Click **"Create"**
5. All 20 beds created and marked ✅ **Available**

**Track Occupancy:**
1. Click **"Ward Occupancy"** dashboard
2. Shows:
   - **Cardiology:** 15/20 beds occupied (75%)
   - **ICU:** 8/10 beds occupied (80%)
   - Trend: Growing/stable/declining
3. See which beds occupied:
   - A-100 (Kwame Owusu - Day 2 post-op)
   - A-101 (Ama Mensah - Day 5, ready for discharge)
   - Etc.

**Tips:**
- Monitor occupancy weekly
- If > 90% full, consider adding beds or encouraging discharge
- Use occupancy data for capacity planning

---

#### 3. Audit Logs

**Scenario:** Security review. Check who accessed patient records.

**Steps:**
1. Click **"Compliance"** → **"Audit Logs"**
2. Filters available:
   - **Date Range:** Last 30 days
   - **Action:** CREATE / READ / UPDATE / DELETE / VIEW
   - **Resource Type:** Patient / Prescription / Lab / Encounter
   - **User Role:** Doctor / Nurse / Admin (filter for doctors only)
   - **Status:** Success / Failed (show only failures)
3. Results show:
   - **Timestamp:** 2025-01-15 14:35:22
   - **User:** Dr. Kwame Adjei
   - **Action:** VIEW Patient Record
   - **Resource:** GHA-2025-001 (patient ID, not name for privacy)
   - **Hospital:** Korle-Bu Teaching Hospital
   - **IP Address:** 192.168.1.100

**Audit Use Cases:**
- **Check who accessed patient:** Filter by patient ID and date
- **Track error patterns:** Filter by "Failed" status
- **Compliance review:** Export last 90 days for auditor
- **Investigate suspicious activity:** Filter by unusual times (e.g., 3 AM) or users

**Export & Report:**
1. Apply filters
2. Click **"Export as CSV"**
3. File downloads with all records
4. Send to compliance officer or auditor

**Tips:**
- Audit logs legally required for healthcare
- Logs kept for 7 years (or longer if required)
- Can't delete logs; only view/report
- Suspicious access (break-glass, after-hours) flagged automatically

---

#### 4. Analytics Dashboard

**Scenario:** Monthly review. Check hospital performance.

**Steps:**
1. Click **"Analytics"** in sidebar
2. Dashboard shows:

   **Patient Volume:**
   - New patients this month: 245
   - Total active patients: 3,840
   - Admissions this month: 89
   - Discharges this month: 85

   **Appointment Performance:**
   - Scheduled appointments: 450
   - Completed: 420 (93%)
   - No-shows: 25 (5.5%)
   - Cancellations: 5 (1%)

   **Clinical Activity:**
   - Lab orders: 1,200
   - Prescriptions written: 890
   - Referrals sent: 45
   - Referrals received: 52

   **AI Usage (if enabled):**
   - AI analyses run: 234
   - Recommendations accepted: 198 (84%)
   - Recommendations rejected: 36 (15%)

   **Workforce:**
   - Active doctors: 25
   - Active nurses: 60
   - Active staff: 150
   - Staff on leave: 8

3. **Trends:** Click on any metric to see 30-day or 90-day trend
   - Line graph showing daily/weekly values
   - Arrows: ↑ Increasing / ↓ Decreasing / → Stable

**Performance Targets:**
- Appointment completion rate: > 90% (yours: 93% ✅)
- No-show rate: < 10% (yours: 5.5% ✅ Excellent!)
- Average wait time: < 30 min (yours: 22 min ✅)
- Lab turnaround: < 2 hours (yours: 2.3 hours ⚠️ Needs improvement)

**Tips:**
- Review metrics monthly with department heads
- Celebrate good performance
- Address declining metrics immediately
- Use data to justify staff hiring or equipment purchases

---

#### 5. Billing & NHIS Claims

**Scenario:** Month end. Submit billing for insurance reimbursement.

**Steps:**
1. Click **"Billing"** → **"Invoices"**
2. View list of invoices:
   - Patient: Kwame Owusu
   - Amount: GHS 500
   - Status: Pending Payment
   - Insurance: NHIS
   - Date: 2025-01-15
3. **Create Invoice** (if not auto-generated):
   - Click **"+ New Invoice"**
   - Select patient and service/procedure
   - System auto-calculates cost based on tariff
   - Submit
4. **Submit NHIS Claim:**
   - Click invoice
   - Click **"Submit to NHIS"**
   - System generates HL7 message with patient, diagnosis, service details
   - Sends to NHIS portal
   - Claim status: **"Submitted"** ⏳
5. **Track Payment:**
   - Status changes to **"Approved"** (NHIS approved)
   - Or **"Rejected"** with reason (e.g., "Invalid diagnosis code")
6. **Payment Received:**
   - Status: **"Paid"** ✅
   - Invoice marked complete

**Tips:**
- Ensure diagnosis codes correct (ICD-10) before submitting
- Batch submit claims weekly, not daily (more efficient)
- Track rejection rates and fix common errors
- Patient responsible for copay if any

---

#### 6. Cross-Facility Governance

**Scenario:** Korle-Bu sends referral to your hospital. Approve cross-facility access.

**Steps:**
1. Click **"Cross-Facility"** → **"Pending Consents & Referrals"**
2. See:
   - **Incoming Referrals:** "Kwame Owusu from Korle-Bu for Cardio surgery"
   - **Pending Consents:** "Ama Mensah - Korle-Bu requesting access to our records"
3. **Approve Referral:**
   - Click referral
   - Review: Patient info, clinical summary, urgency
   - Click **"Accept Referral"** → Patient care now at your hospital
   - Or **"Reject"** with reason if capacity issue
4. **Grant Consent:**
   - Click consent request
   - Review: What data they're requesting (SUMMARY or FULL_RECORD)
   - Click **"Grant"** (patient has already consented via their hospital)
   - Or **"Deny"** if data concerns
5. **View Your Referrals Out:**
   - See where you've referred patients
   - Track acceptance status
   - Follow up if not accepted within 48 hours

**Tips:**
- Cross-facility improves patient care and network reputation
- Consent is bi-directional but managed separately
- Always verify patient identity before granting access

---

### Troubleshooting

**"New staff can't log in"**
- Check if activation link was sent to correct email
- Ask staff if they created password (it's required, not optional)
- Check MFA setup—did they scan QR code?
- Force password reset if needed

**"Can't create ward"**
- Check ward name not already in use
- Check number of beds is positive (> 0)
- Try again or contact IT

**"Audit log download very slow"**
- If exporting > 1 year data, may take minutes
- System generates in background; you'll get email when ready
- Or narrow date range to speed up

---

### Common Workflows

#### Monthly Admin Check (1 hour)

1. **Review analytics** → Check key metrics vs targets (15 min)
2. **Audit logs** → Spot-check for suspicious access (10 min)
3. **Staff management** → Check for pending activations (5 min)
4. **Billing** → Review submissions and rejections (15 min)
5. **Cross-facility** → Approve pending referrals/consents (5 min)
6. **Email report** → Monthly summary to hospital leadership (10 min)

---

---

## Super Admin / System Administrator

### Overview

As a super admin, you have full system access across all hospitals. You'll use MedSync to:
- **Manage all hospitals** and their onboarding
- **Global audit logs** (system-wide activity)
- **Security & compliance** (break-glass use, suspicious activity)
- **System health** (database, AI, background jobs)
- **AI deployment** (enable/disable AI features per hospital)
- **Network analytics** (cross-facility referrals, HIE activity)
- **Break-glass oversight** (emergency record access review)

### Key Features

#### 1. Hospital Onboarding

**Scenario:** New hospital "Golden Clinic" joins the network. Onboard them.

**Steps:**
1. Click **"System Admin"** → **"Onboard New Hospital"**
2. Fill hospital details:
   - **Hospital Name:** Golden Clinic
   - **Location:** Kumasi, Ghana
   - **Hospital Code:** GC-001
   - **Contact Email:** admin@goldenclinic.gh
   - **Contact Phone:** +233-0-XXX-XXXX
   - **Specialties:** General Practice / Maternity / Pediatrics
3. Click **"Create Hospital"**
4. System generates:
   - Hospital ID (uuid)
   - Admin user account (temporary password)
   - Initial database schema (isolated data)
5. **Next Step: Invite Admin**
   - Click **"Invite Hospital Admin"**
   - System sends email to admin@goldenclinic.gh
   - Admin creates account and password
   - Admin can now log in and start inviting staff

**Setup Wizard (Auto-guides Hospital Admin):**
- After admin logs in first time, guided through:
  1. Create departments (General, Maternity, etc.)
  2. Create wards and beds
  3. Invite doctors and nurses
  4. Configure billing/insurance
  5. Enable optional features (AI, FHIR export, etc.)

**Tips:**
- Onboarding takes 2-3 hours typically
- Admin support available during setup
- Once live, hospital data is isolated (other hospitals can't see)

---

#### 2. Global Audit Logs

**Scenario:** Security review. Check system-wide activity for anomalies.

**Steps:**
1. Click **"System Admin"** → **"Global Audit Logs"**
2. See all actions across all hospitals:
   - Hospital: Korle-Bu Teaching Hospital
   - User: Dr. Kwame Adjei
   - Action: VIEW Patient (cross-facility with break-glass)
   - Patient ID: GHA-2025-001
   - Timestamp: 2025-01-15 14:35:22
   - Result: Success
3. **Filter by:**
   - **Hospital:** (default: all hospitals)
   - **User Role:** Doctor / Nurse / Admin / Super Admin
   - **Action Type:** VIEW / CREATE / UPDATE / DELETE / EMERGENCY_ACCESS
   - **Date Range:** Last 7 days / 30 days / custom
4. **Flag unusual patterns:**
   - User accessing many patients (data breach?)
   - Break-glass use spike (real emergencies or abuse?)
   - Unusual times (3 AM access when clinic closed?)
5. **Investigate:**
   - Click log entry for details
   - See user info, exact resource accessed, IP address
   - Contact hospital admin if suspicious

**Compliance Export:**
- Click **"Export for Audit"**
- Download 365-day audit trail
- Provide to external auditors / regulators
- Proves full traceability of record access

**Tips:**
- Monitor break-glass use weekly
- Flag if > 3 per day at any hospital (may indicate abuse)
- Check for deleted audit logs (shouldn't happen—logs immutable)

---

#### 3. Break-Glass Oversight

**Scenario:** Weekly review. Ensure break-glass feature not being abused.

**Steps:**
1. Click **"System Admin"** → **"Break-Glass Activity"**
2. See all break-glass accesses across network:
   - Hospital: Ridge Regional Hospital
   - User: Dr. Ama Kusi
   - Patient: Kwame Owusu
   - Reason: EMERGENCY_TREATMENT
   - Duration: 15 minutes (started 14:30, ended 14:45)
   - Timestamp: 2025-01-15 14:30
   - Status: Under Review
3. **Assess if legitimate:**
   - Reason makes sense? (Emergency use OK)
   - Timeframe appropriate? (15 min is max, good)
   - After-hours? (OK if genuine emergency, suspicious if routine)
   - Frequency per user? (1 use OK; 5+ per month = potential abuse)
4. **Mark Reviewed:**
   - Click **"Mark Reviewed"** → Status: ✅ **Legitimate**
   - Or click **"Flag for Investigation"** → Status: 🚨 **Suspicious**
5. **If Suspicious:**
   - System creates case for follow-up
   - Email sent to hospital admin: "Possible break-glass misuse by Dr. Ama Kusi"
   - Admin investigates and reports back
   - Disciplinary action if confirmed abuse

**Break-Glass Guidelines:**
- ✅ Legitimate: Unconscious patient, unknown allergies, emergency room triage
- ❌ Abuse: Convenience (consent could have been requested), curiosity, routine check-up

**Monthly Report:**
- Total break-glass uses: 45
- Legitimate: 44 (98%)
- Suspicious: 1 (2%)
- Trend: Stable (good)

**Tips:**
- Trust healthcare workers; assume legitimate unless clear pattern
- Over-policing breaks trust
- Under-monitoring misses abuse

---

#### 4. System Health Dashboard

**Scenario:** Daily check. Ensure all systems operational.

**Steps:**
1. Click **"System Health"** dashboard
2. Overview of all components:
   - **API Status:** ✅ Healthy
     - Response time (p99): 185ms (target < 500ms)
     - Error rate: 0.08% (target < 1%)
     - Requests/second: 45 (within capacity)
   - **Database:** ✅ Healthy
     - Connection pool: 15/20 (good, not maxed)
     - Query latency (p95): 78ms (target < 300ms)
     - Disk usage: 450GB / 500GB (90%, getting full!)
   - **Redis Cache:** ✅ Healthy
     - Hit rate: 88% (target > 80%)
     - Memory: 1.2GB / 4GB (fine)
     - Evictions: Low
   - **AI Model:** ✅ Healthy
     - Requests queue: 8 (manageable)
     - Avg response time: 1.2s (target 1-2s)
     - Model version: v2.1 (current)
   - **Background Jobs:** ✅ Healthy
     - Pending: 12 (target < 50)
     - Failed (24h): 0 (target < 5)
     - Queue wait time: 2s
3. **Alerts:**
   - 🟡 **Disk Usage 90%:** Consider archiving old logs or adding storage
   - No critical alerts ✅

**Performance Targets:**
- API response < 500ms: 95% of requests
- Error rate < 1%
- Database latency < 300ms for 95th percentile
- Cache hit rate > 80%
- Background job queue < 50 tasks

**When to Escalate:**
- API response > 1s: Page engineer
- Error rate > 5%: Page manager
- Database down: Immediate escalation
- Disk full (> 95%): Add storage ASAP

**Tips:**
- Check daily during business hours
- Set up automated alerts for critical issues
- Archive old logs to free disk space regularly

---

#### 5. AI Deployment Management

**Scenario:** Hospital admin requests AI features. Review and approve.

**Steps:**
1. Click **"System Admin"** → **"AI Deployments"**
2. See pending requests:
   - **Hospital:** Ridge Regional Hospital
   - **Features Requested:** Comprehensive patient analysis, Risk prediction
   - **Status:** Pending Approval
   - **Requested by:** Hospital Admin Dr. Ama
   - **Date Requested:** 2025-01-10

3. **Review Request:**
   - Check hospital: ✅ Active and in good standing
   - Check staff trained?: Ask admin (may need training first)
   - Check infrastructure: Hospital has GPU? (AI uses GPU)
   - Check data quality: Sufficient historical data for AI to learn?
4. **Approve or Deny:**
   - Click **"Approve"** → AI enabled immediately at hospital
     - Doctors see AI options in patient records
     - AI starts analyzing patients
   - Or click **"Deny"** with reason:
     - "Hospital needs GPU for AI acceleration"
     - "Staff needs training first"
5. **Monitor After Deployment:**
   - Track AI recommendations usage
   - Monitor if recommendations being accepted/rejected
   - Check for errors in AI outputs

**AI Performance Metrics (per hospital):**
- **Ridge Regional Hospital:**
  - AI enabled: 3 weeks
  - Analyses run: 234
  - Avg confidence score: 76%
  - Recommendations accepted: 82%
  - Performance: Good ✅

**Disable AI (if issues):**
- Click **"Disable AI"** → Doctors no longer see AI features
- May be needed if: High error rate, false recommendations, patient safety concern
- Hospital admin notified of disabling

**Tips:**
- Enable AI for active, engaged hospitals first
- Smaller hospitals may not need AI (low volume)
- Monitor outcomes after deployment

---

#### 6. Network Analytics (Cross-Facility)

**Scenario:** Quarterly review. Analyze how well network is functioning.

**Steps:**
1. Click **"System Admin"** → **"Network Analytics"**
2. Dashboard shows:

   **Referral Network:**
   - Total referrals this quarter: 450
   - Acceptance rate: 94% (high, good!)
   - Avg time to acceptance: 2.3 hours
   - Top referring hospital: Korle-Bu Teaching Hospital (150 referrals)
   - Top receiving hospital: Ridge Regional Hospital (140 referrals)

   **Consent & Cross-Facility Access:**
   - Total consents granted: 325
   - Consents revoked: 8 (2.5%)
   - Cross-facility records viewed: 1,200
   - Avg scope: 60% FULL_RECORD, 40% SUMMARY

   **Interoperability Health:**
   - FHIR exports: 450 (OK)
   - FHIR import errors: 2 (acceptable)
   - HL7 ADT messages sent: 1,200
   - Failed messages: 1 (good, < 0.1%)

   **Network Growth:**
   - New patients entered network: 120
   - Patient transfers between hospitals: 85
   - Global patient IDs created: 50
   - Duplicate patient merges: 3

3. **Health Assessment:**
   - ✅ Network is thriving
   - Referral acceptance high → Hospitals trust each other
   - Consent rate good → Patients engage with HIE
   - Interoperability errors low → Systems communicating well

**Bottlenecks:**
- If referral acceptance < 80%: Investigate delays, train staff
- If consent rate < 50%: Launch awareness campaign to patients
- If interop errors > 1%: Debug HL7/FHIR mapping

**Tips:**
- Quarterly review adequate (network doesn't change hourly)
- Share results with hospital leaders to celebrate success
- Use data to justify more funding for interoperability

---

### Troubleshooting

**"Suspicious break-glass use flagged—what now?"**
- Contact hospital admin by email
- Ask for explanation: Was there true emergency?
- Request incident report from user
- If user confirms legitimate, mark reviewed and close
- If no response within 48 hours, escalate to regional director

**"AI deployment failing at hospital"**
- Check hospital's GPU available: Can't run AI without GPU (or it's very slow)
- Verify hospital staff trained on AI feature
- Run diagnostics: Is model loading correctly?
- If issue persists > 24 hours, disable temporarily and investigate

**"Database disk 95% full"**
- Archive old audit logs: `python manage.py archive_audit_logs --older_than_days=365`
- Clean up old batch jobs: `python manage.py cleanup_batch_jobs --older_than_days=90`
- Add more disk space to server
- Priority: Don't let system run out of disk (can cause data corruption)

---

### Common Workflows

#### Daily Super Admin Check (30 min)

1. **System health** → Verify all green (5 min)
2. **Audit review** → Check for suspicious patterns (10 min)
3. **Break-glass review** → Spot-check uses (5 min)
4. **Alert log** → Any critical issues? (5 min)
5. **Email report** → Summary to leadership (5 min)

---

---

## Common Issues & Escalation

### When to Contact Support

| Issue | Who to Contact | Urgency |
|-------|---|---|
| Can't log in | Your hospital IT admin | High |
| Patient data missing | Your hospital IT admin + MedSync support | Critical |
| Feature not working (e.g., can't submit lab results) | Feature owner (contact hospital admin) | High |
| Hospital feature request (e.g., "Need new ward type") | MedSync product team via hospital admin | Low |
| Question about how to use feature | Your supervisor or trainer | Medium |
| Security concern (e.g., suspicious user access) | Hospital admin + MedSync security team | Critical |
| AI recommendation seems wrong | Your supervising doctor + MedSync AI team | Medium |
| Appointment not showing for patient | Your receptionist or IT admin | Medium |

### Quick Support Contacts

- **Hospital IT Help Desk:** Usually on-site or nearby
- **MedSync Support Email:** support@medsync.gh
- **MedSync Support Phone:** +233-0-XXX-XXXX (business hours)
- **MedSync Emergency Line:** +233-0-YYY-YYYY (after hours, for system down only)

---

**Version 1.0 | Published 2025**  
**Questions? Contact your hospital admin or MedSync support team.**
