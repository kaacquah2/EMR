# Chapter 1: Project Overview & Requirements

## 1.1 Introduction
MedSync EMR is a centralized, multi-hospital Electronic Medical Records (EMR) system tailored for the Ghanaian healthcare ecosystem. It serves as an interoperable bridge across the country's tiered healthcare facilities—ranging from Community Health Planning and Services (CHPS) compounds and local Health Centres to District, Regional, and Teaching Hospitals. By establishing a unified record network, MedSync addresses critical gaps in data fragmentation, clinical safety, patient tracking, and regulatory compliance.

## 1.2 Problem Statement
In developing nations like Ghana, patient records are traditionally stored in siloed physical logbooks or standalone local databases. When a patient is referred from a rural CHPS compound to a regional teaching hospital:
1. **Clinical Data Fragmentation:** Their medical history, allergy alerts, and past treatments do not travel with them, forcing clinicians to make decisions based on incomplete info.
2. **Global Identity Resolution:** There is no national unified master patient index, leading to duplicated records and identity mismatching.
3. **Data Protection Compliance:** Cross-facility data sharing often lacks structured consent frameworks, violating regulations like the **Ghana Data Protection Act (NDPA 2012)** and international standards like **HIPAA**.
4. **Emergency Overrides:** In critical care or life-threatening emergencies, doctors cannot quickly override restrictions to view patient vitals or records without an audited "Break-Glass" workflow.

MedSync EMR solves these challenges by combining a secure, multi-tenant hospital EMR system with a global patient registry, consent-gated data-sharing protocols, and rigorous security hardening.

---

## 1.3 Functional Requirements

MedSync's functionality is structured around four primary domains:

### 1.3.1 Administrative & Hospital Management
- **Hospital Onboarding:** Super Admins can onboard new healthcare facilities into the network and configure their details (region, nhis_code, tier).
- **Staff Provisioning:** Hospital Admins can onboard staff, configure department links, assign roles, and manage system status.
- **Physical Layout Mapping:** Facilities can map their wards, department units (OPD, lab, pharmacy, radiology), and track individual bed statuses (available, occupied, maintenance).

### 1.3.2 Clinical Records & Patient Intake
- **Patient Registration:** Receptionists register local patients, inputting demographic information and resolving duplicates.
- **Vitals & Encounters:** Nurses record patient admission events, vitals (vitals tracking logs), and clinical notes. Doctors create clinical encounters, record diagnoses, and draft treatment plans.
- **Emergency Department Triage:** Incorporates color-coded emergency triage categorization (Red, Yellow, Green, Blue) with room assignments and arrival logs.

### 1.3.3 Diagnostic & Therapeutic Workflows
- **Lab Order Lifecycles:** Doctors issue lab orders; lab technicians perform tests, input findings, and submit results which feed back into the patient’s file.
- **Pharmacy & MAR:** Doctors prescribe medications; pharmacy technicians verify inventory, manage the pharmacy queue, and record dispensation status using the Medication Administration Record (MAR).

### 1.3.4 Inter-Hospital Interoperability (HIE)
- **Global Patient Registry (GPID):** Generates and maps unique cross-facility IDs based on National ID (Ghana Card), NHIS, or passport numbers.
- **Consent Gateways:** Patients grant or revoke SUMMARY or FULL_RECORD scopes for external hospitals.
- **Referral Workflows:** Enables secure referrals between hospitals, linking shared diagnostic histories and records.
- **Emergency Break-Glass:** Facilitates emergency, audit-logged access to critical summaries for unconscious or incapacitated patients.

---

## 1.4 Non-Functional Requirements

### 1.4.1 Security & Cryptography
- **Multi-Factor Authentication (MFA):** Mandatory for all clinical roles via Time-based One-Time Passwords (TOTP) or secure Passkeys (WebAuthn).
- **Password Hardening:** Minimum 12-character passwords with complexity constraints, a 5-password historic reuse block, and a 5-attempt brute-force lockout (15-minute cooldown).
- **Audit Trails:** Chained, tamper-evident audit logging with SHA-256 and HMAC signatures to guarantee that log entries cannot be modified or deleted post-hoc.
- **Field-Level Encryption:** Sensitive Protected Health Information (PHI) like national IDs, passport numbers, and dates of birth are encrypted at rest within the database.

### 1.4.2 Regulatory Compliance
- **Ghana NDPA 2012:** Restricts cross-border transfers and enforces local data residency (data residency locked) unless explicit consent is provided. Enforces patient rights to withdraw consent at any time.
- **HIPAA:** Aligns with standard practices for administrative safeguards, physical safeguards, and technical safeguards (transmission security, unique user identification, emergency access).

### 1.4.3 Performance & Reliability
- **Multi-Tenancy Scoping:** Ensures query isolation so a user at one hospital can never query another hospital's local database scope (fail-closed architecture).
- **Responsive Web UI:** High-fidelity dashboards configured specifically for desktops, tablets, and mobile devices inside active clinical wards.

---

## 1.5 Role-Based Access Matrix

The system maps access to dashboards and core features across **10 distinct user roles**:

| Role | Hospital Scope | Primary Dashboard Views | Crucial Operations |
| :--- | :--- | :--- | :--- |
| **super_admin** | Global (Cross-Hospital) | Hospital onboarding, global audit trails, admin management | Provision hospital admin credentials, view global system logs |
| **hospital_admin** | Single Hospital | Staff profiles, ward setup, facility audit trail | Manage staff status, configure wards/departments, review break-glass events |
| **doctor** | Single Hospital | Patient lists, clinical encounters, lab/rx orders | Register diagnosis, write prescriptions, issue referrals, trigger break-glass |
| **nurse** | Single Hospital | Ward patients, bed manager, vitals logs | Record vitals, execute admissions, manage bed status |
| **lab_technician** | Single Hospital | Lab order worklist, test entry sheets | Accept orders, input test findings, publish results |
| **radiology_technician** | Single Hospital | Imaging order queue, file upload interface | Upload imaging scans, compile radiologist reports |
| **pharmacy_technician**| Single Hospital | Prescription queue, MAR sheets, stock balance | Dispense medication, update stock balances, mark MAR administration |
| **receptionist** | Single Hospital | Appointment lists, registration form | Update demographics, schedule appointments, check-in patients |
| **billing_staff** | Single Hospital | Invoice records, NHIS claims dashboard | Issue invoices, process cash/card/NHIS payments |
| **ward_clerk** | Single Hospital | Bed status panels, ward administration | Track bed occupancies, assign incoming patients to empty beds |
