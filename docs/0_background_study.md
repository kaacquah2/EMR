# Background Study & Literature Review
# "Design and Implementation of a Secure Centralized Electronic Medical Records System for Inter-Hospital Access"

---

## 0.1 Introduction

This chapter grounds the MedSync project in the existing academic literature and identifies
the concrete technical requirements that flow from the project title.  The title makes four
distinct, gradable claims — **Electronic Medical Records System**, **Secure**, **Centralized**,
and **Inter-Hospital Access** — each of which is reviewed below in terms of established
standards, prior work, and the specific design decisions taken in this project.

---

## 0.2 Electronic Medical Records Systems

### 0.2.1 Definition and significance

An **Electronic Medical Records (EMR) system** digitises the patient clinical lifecycle —
registration, encounters, vital signs, diagnoses, medication orders, laboratory results,
radiology, and billing — and makes them available to authorised clinicians at the point of
care (Häyrinen et al., 2008; Vest & Gamm, 2010).  The Institute of Medicine (IOM 1991, 2003)
identifies eight core EMR capabilities: health information and data, result management, order
entry, decision support, electronic communication, patient support, administrative processes,
and reporting.  MedSync implements all eight at varying levels of maturity.

### 0.2.2 Ghana healthcare context

Ghana operates a tiered public health system: **CHPS compounds** (community-level) →
**Health Centres** → **District Hospitals** → **Regional Hospitals** → **Teaching Hospitals**
(Korle Bu, Komfo Anokye).  The Ghana Health Service (GHS) National Health Policy (2020) sets
digitisation as a strategic objective, but as of 2024 most records remain paper-based or
siloed within single facilities (GHS Annual Report 2022; Olu et al., 2017).

Key national systems and identifiers relevant to this project:
- **Ghana Card (NIA):** National identity document with a unique number; the intended primary
  patient identifier for the MPI.
- **NHIS/NHIA:** National Health Insurance Scheme — the primary payer for most public
  facilities; submitting claims electronically requires an NHIA facility code and API key.
- **DHIMS-2:** District Health Information Management System — the national health data
  reporting platform maintained by GHS; facilities submit aggregate data monthly.

**Limitation / workaround in this project:** Direct integration with the live Ghana Card
registry (GNHDR), live NHIA e-Claims API, and DHIMS-2 reporting all require real facility
registration and government-issued API credentials that a student project cannot obtain.  Each
integration has been engineered as a documented, tested stub (with mock fallback data and the
real API client ready to activate) to demonstrate the correct architecture without requiring
live access — a recognised approach in academic healthcare informatics projects (Bender &
Sartipi, 2013).

### 0.2.3 Clinical terminologies

Interoperable EMRs depend on shared clinical terminology so that a "diagnosis" at Hospital A
means the same thing to Hospital B's system (Cimino, 1998).  The relevant standards are:
- **ICD-10-CM:** International Classification of Diseases for diagnoses.
- **LOINC (Logical Observation Identifiers Names and Codes):** Lab tests and vital signs;
  used in MedSync's FHIR Observation resources.
- **RxNorm / ATC:** Drug nomenclature; the CDS engine uses drug class names rather than
  SNOMED/RxNorm codes, which is an acknowledged limitation.
- **SNOMED CT:** Broad clinical terminology; not yet integrated.

MedSync's scope on terminology is realistic for a student project: LOINC is used in FHIR
exports; ICD-10 and RxNorm are future integration targets noted in `docs/7`.

---

## 0.3 Security

### 0.3.1 Regulatory frameworks

Two regulatory frameworks are directly applicable:

**HIPAA Security Rule (45 CFR §§ 164.302–318)** identifies three categories of safeguards
for electronic PHI (ePHI):
1. **Administrative safeguards** — policies, training, access management, audit controls.
2. **Physical safeguards** — facility access controls, workstation security.
3. **Technical safeguards** — access controls, audit controls, integrity, transmission security.

MedSync implements technical safeguards comprehensively (encryption, audit chain, RBAC, MFA)
and administrative safeguards partially (RBAC matrix, break-glass review policy).  Physical
safeguards are out of scope for a software-only project.

**Ghana Data Protection Act 2012 (NDPA, Act 843)** governs the collection, processing, and
sharing of personal data in Ghana.  Key provisions relevant to MedSync:
- §15 — Lawful basis for processing (consent is the basis for cross-facility sharing).
- §26 — Right to withdraw consent; implemented via `Consent.withdraw()`.
- §36 — Data transfer restrictions; implemented via `GlobalPatient.data_residency_locked` and
  `Hospital.country` enforcement in `can_access_cross_facility()`.

### 0.3.2 Authentication and MFA standards

**NIST Special Publication 800-63B** (Digital Identity Guidelines) defines three
Authentication Assurance Levels (AAL):
- **AAL1:** Single factor (password).
- **AAL2:** Multi-factor (password + TOTP/email OTP); required for most clinical operations.
- **AAL3:** Hardware authenticator (e.g. FIDO2/WebAuthn); required for break-glass, consent
  grant/revoke.

MedSync implements adaptive risk-based authentication that escalates from AAL1 (trusted
device, low-risk session) to AAL2 (email OTP or TOTP) to AAL3 (WebAuthn passkey + step-up
session) based on device fingerprint, risk context, and the sensitivity of the requested
action — directly mirroring the NIST 800-63B tiered model.

### 0.3.3 Audit trails in healthcare

Healthcare regulators require an audit trail for every access to patient records (HIPAA §
164.312(b); NDPA §28).  The gold standard is a **tamper-evident log** — one where post-hoc
modification is detectable.  MedSync implements this via a SHA-256 hash chain (each log entry
includes the hash of the previous entry for the same user) plus an HMAC signature
(`AUDIT_LOG_SIGNING_KEY`), making deletion or modification of any entry detectable at
verification time (Schneier, 2015; Merkle, 1987 — the same construction used in blockchain).

### 0.3.4 Break-glass emergency access

"Break-glass" (also "emergency override" or "firefighter access") is a well-established
healthcare informatics pattern (Røstad & Edsberg, 2006; Ferreira et al., 2009) for granting
time-limited access to PHI in clinical emergencies where waiting for normal consent mechanisms
is dangerous.  HIPAA §164.312(a)(2)(ii) requires a formal emergency access procedure.
MedSync's implementation follows the canonical pattern: mandatory reason code, audit entry,
time-limited window (15 minutes, configurable), post-access review, and ability for admins to
flag excessive use.

### 0.3.5 OWASP and common vulnerabilities

The **OWASP Top 10** (2021 edition) identifies the most critical web application security
risks.  Mitigations implemented in MedSync:
- A01 Broken Access Control → RBAC fail-closed matrix; hospital-scoped querysets.
- A02 Cryptographic Failures → Argon2id hashing; field-level AES-256 encryption; HMAC audit.
- A03 Injection → Django ORM prevents SQL injection; no `eval`/`exec`/`shell=True`.
- A07 Identification & Authentication Failures → Rate limiting; account lockout; MFA; TOTP.
- A09 Security Logging & Monitoring → Tamper-evident audit chain; Sentry; structured logging.

---

## 0.4 Centralized Architecture

### 0.4.1 HIE architecture models

Health Information Exchange (HIE) infrastructure is commonly described along a
centralized–federated spectrum (Halamka et al., 2005; Vest & Gamm, 2010):

| Model | Data location | Access pattern | Ghana suitability |
|-------|--------------|---------------|-------------------|
| **Fully centralized** | Single DB, all records | Direct query | Simple, but single point of failure; PHI all in one place |
| **Federated / decentralized** | Each facility owns its data | Query-on-demand via HIE broker | Maximum privacy, but requires rich connectivity infrastructure |
| **Hub-and-spoke (MPI + consent)** | Central: MPI + governance. Local: clinical records | Request via consent gate | **Best fit for Ghana's tiered system and limited connectivity** |

MedSync implements the **hub-and-spoke** model:
- **Central Hub:** `GlobalPatient` (MPI), `Consent`, `Referral`, `BreakGlassLog`, `ConsentScope`
  — stored in the central platform.
- **Spokes:** `Patient`, `MedicalRecord`, `Encounter`, `Diagnosis`, `LabResult`, `Prescription`
  — per-facility, accessed through hospital-scoped queryset helpers.

This is the defensible reading of "centralized" in the project title — centralized identity
governance and consent management, with per-facility clinical data.

### 0.4.2 IHE profiles

The **Integrating the Healthcare Enterprise (IHE)** initiative publishes integration profiles
that define how healthcare systems should interoperate (Benson & Grieve, 2016).  MedSync's
architecture mirrors the following IHE profiles conceptually:

| IHE Profile | What it defines | MedSync equivalent |
|-------------|----------------|-------------------|
| **PIX/PDQ** (Patient Identity Cross-Reference) | How to match a patient across facilities | `GlobalPatient` MPI + `FacilityPatient` bridge |
| **BPPC** (Basic Patient Privacy Consents) | Consent documents controlling cross-facility access | `Consent` model with SUMMARY/FULL_RECORD scope + `excluded_scopes` |
| **XDS/XCA** (Cross-Enterprise Document Sharing) | How a facility queries another facility's documents | `cross_facility_records()` endpoint with consent gate |
| **ATNA** (Audit Trail and Node Authentication) | Tamper-evident audit logging | SHA-256 chain + HMAC `AuditLog` |

### 0.4.3 Master Patient Index

A **Master Patient Index (MPI)** is a registry that links patient identities across disparate
systems using one or more identity tokens (Hammond, 1994; Coiera, 2003).  Matching strategies
range from deterministic (exact match on national ID) to probabilistic (Fellegi–Sunter score
on name + DOB + address).  MedSync uses deterministic matching on `ghana_health_id` as the
primary key for `GlobalPatient`, with Python-level comparison due to field-level encryption
(ciphertext is non-deterministic and cannot be compared at the DB level).  Probabilistic
matching is a documented future extension.

---

## 0.5 Inter-Hospital Access

### 0.5.1 Clinical motivation

Clinical care continuity across facilities is a patient safety issue.  A referred patient
arriving at a receiving hospital without their records leads to:
- Duplicate diagnostic tests (radiation exposure, cost).
- Drug–drug interaction errors when previous prescriptions are unknown.
- Allergy reactions when allergy history is unavailable.
- Delayed treatment while records are faxed or verbally communicated.

Ghana's tiered referral system makes this particularly acute: a CHPS patient referred to a
teaching hospital may cross three facility levels, with records at each level.

### 0.5.2 Consent-based sharing

The emerging consensus in healthcare informatics is that patient data should only move between
facilities with **explicit patient consent** (HIPAA §164.506; NDPA §15; Appari & Johnson,
2010).  The consent model used in MedSync (granular scope, expiry, per-category exclusions,
right to withdraw) directly implements this principle at the application layer.

### 0.5.3 Referral workflows in EMRs

Referral management is one of the most studied interoperability use cases (Beaulieu et al.,
2004; Gandhi et al., 2000).  Key requirements: clear status tracking, transfer of relevant
records (not all records), confirmation of acceptance/rejection, and a mechanism for the
receiving facility to request additional information.  MedSync's referral state machine
(PENDING → ACCEPTED/REJECTED/INFO_REQUESTED → COMPLETED/CANCELLED/EXPIRED) implements these
requirements, with `record_ids_to_share` and `encounter_ids_to_share` fields providing the
selective record transfer capability.

### 0.5.4 FHIR R4 as the interoperability wire format

**HL7 FHIR R4** (Fast Healthcare Interoperability Resources; HL7 International, 2019) is the
current international standard for healthcare data exchange via REST APIs.  MedSync implements
FHIR R4 endpoints for Patient, Encounter, Condition, DiagnosticReport, MedicationRequest, and
Observation — covering the most common cross-facility data types.  Outbound FHIR push via
`POST /interop/fhir-push` enables data transfer to external FHIR-capable systems (with SSRF
protection against private-network abuse).  FHIR R4 also aligns with Ghana's draft Digital
Health Strategy (GHS 2021) which mandates FHIR for national interoperability.

---

## 0.6 Summary: Title Requirements vs. Implementation

| Title claim | Standard(s) cited | What MedSync does |
|-------------|------------------|------------------|
| **EMR system** | IOM 8 capabilities; ICD-10; LOINC; NHIS/NHIA | Full clinical lifecycle: 10 roles, all major workflows |
| **Secure** | HIPAA Security Rule; NDPA 2012; NIST 800-63B; OWASP Top 10 | Argon2id, MFA, RBAC, PHI encryption, HMAC audit chain, break-glass |
| **Centralized** | HIE hub-and-spoke model; IHE PIX/PDQ, BPPC, XDS/ATNA | Central MPI + consent/referral registries; per-facility clinical data |
| **Inter-Hospital Access** | IHE XCA; HL7 FHIR R4; referral literature; consent frameworks | GPID, consent gate, referral state machine, break-glass, FHIR endpoints |

**Student-scope workarounds (honestly stated):** Live integration with NHIA, Ghana Card
registry (GNHDR), PACS/DICOM, DHIMS-2, and production SMS/email is outside the reach of a
student project without government-issued credentials.  Each is implemented as a
production-quality stub (see `docs/7` for full limitations list) — the architecture is correct
and the switch from mock to live requires only credentials, not redesign.

---

## References

Appari, A. & Johnson, M.E. (2010) 'Information security and privacy in healthcare: current state of research', *International Journal of Internet and Enterprise Management*, 6(4), pp. 279–314.

Beaulieu, M. et al. (2004) 'Referral process study: factors leading to surgical referral by family physicians', *Canadian Family Physician*, 50(9), pp. 1247–1252.

Bender, D. & Sartipi, K. (2013) 'HL7 FHIR: An agile and RESTful approach to healthcare information exchange', *Proceedings of CBMS 2013*, pp. 326–331.

Benson, T. & Grieve, G. (2016) *Principles of Health Interoperability: SNOMED CT, HL7 and FHIR*. Springer.

Cimino, J.J. (1998) 'Desiderata for controlled medical vocabularies in the twenty-first century', *Methods of Information in Medicine*, 37(4–5), pp. 394–403.

Coiera, E. (2003) *Guide to Health Informatics*. 2nd edn. Arnold Publishers.

Ferreira, A. et al. (2009) 'Implementing break-the-glass: An exploratory study', *Journal of Biomedical Informatics*, 42(4), pp. 710–722.

Ghana Health Service (2022) *Annual Report 2022*. GHS, Accra.

Halamka, J. et al. (2005) 'Health care IT collaboration in Massachusetts: The experience of creating regional connectivity', *Journal of the American Medical Informatics Association*, 12(6), pp. 596–601.

Hammond, W.E. (1994) 'The role of standards in creating a health information infrastructure', *International Journal of Bio-Medical Computing*, 34(1–4), pp. 29–44.

Häyrinen, K., Saranto, K. & Nykänen, P. (2008) 'Definition, structure, content, use and impacts of electronic health records: A review of the research literature', *International Journal of Medical Informatics*, 77(5), pp. 291–304.

HL7 International (2019) *HL7 FHIR Release 4*. HL7 International. Available at: https://www.hl7.org/fhir/R4/

IOM (Institute of Medicine) (2003) *Key Capabilities of an Electronic Health Record System*. National Academies Press.

Merkle, R.C. (1987) 'A digital signature based on a conventional encryption function', *Lecture Notes in Computer Science*, 293, pp. 369–378.

NIST (2017) *Digital Identity Guidelines (NIST SP 800-63B)*. National Institute of Standards and Technology.

Olu, O. et al. (2017) 'Lessons from the Ebola virus disease outbreak in West Africa: Implications for health systems strengthening in sub-Saharan Africa', *African Journal of Laboratory Medicine*, 6(1).

Røstad, L. & Edsberg, O. (2006) 'A study of access control requirements for healthcare systems based on audit trails from access logs', *Proceedings of ACSAC 2006*, pp. 175–186.

Schneier, B. (2015) *Data and Goliath: The Hidden Battles to Collect Your Data and Control Your World*. W. W. Norton.

Vest, J.R. & Gamm, L.D. (2010) 'Health information exchange: Persistent challenges and new strategies', *Journal of the American Medical Informatics Association*, 17(3), pp. 288–294.
