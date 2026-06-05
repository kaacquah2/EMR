# MedSync System Overview: Multi-Hospital Interoperability

This diagram illustrates the architectural flow of the MedSync EMR system, highlighting how multiple hospitals interact through a centralized health registry and how security mechanisms (Consents & Break-Glass) are audited.

```mermaid
graph TB
    subgraph "Hospital A (Regional Hospital)"
        DocA[Clinician A]
        DBA[(Local EMR DB)]
    end

    subgraph "Hospital B (Specialist Center)"
        DocB[Clinician B]
        DBB[(Local EMR DB)]
    end

    subgraph "MedSync Central Interop Layer"
        Registry{GPID Registry}
        ReferralEngine[Referral Service]
        ConsentService[Consent Manager]
        AuditChain[Chained Audit Log]
        AIDecisionSupport[AI Decision Support]
    end

    subgraph "Super Admin Panel"
        Admin[System Auditor]
    end

    %% Referral Flow
    DocA -- "1. Sends Referral" --> ReferralEngine
    ReferralEngine -- "2. AI Recommendation" --> AIDecisionSupport
    AIDecisionSupport -- "3. Optimal Hospital" --> ReferralEngine
    ReferralEngine -- "4. Notifies" --> DocB
    DocB -- "5. Accepts Referral" --> ReferralEngine
    ReferralEngine -- "6. Grants Temporary Access" --> ConsentService

    %% Data Flow
    DocB -- "5. Requests Records" --> Registry
    Registry -- "6. Validates Access" --> ConsentService
    ConsentService -- "7. Authorized" --> Registry
    Registry -- "8. Aggregates PHI" --> DBA
    Registry -- "8. Aggregates PHI" --> DBB
    Registry -- "9. AI Insights" --> AIDecisionSupport
    AIDecisionSupport -- "10. Clinical Summary" --> DocB
    DocB -- "11. Unified Clinical View" --> DocB

    %% Break-Glass Flow
    DocB -- "Emergency: Break-Glass" --> AuditChain
    AuditChain -- "Alerts" --> Admin
    Admin -- "Reviews Justification" --> AuditChain

    %% Styling
    style Registry fill:#0B8A96,color:#fff
    style AuditChain fill:#f59e0b,color:#fff
    style ReferralEngine fill:#3b82f6,color:#fff
    style ConsentService fill:#10b981,color:#fff
    style AIDecisionSupport fill:#8b5cf6,color:#fff
```

### Key Components:
1.  **GPID Registry**: A centralized database mapping national identities to local facility records.
2.  **Referral Service**: Orchestrates the transfer of patient care between facilities.
3.  **Consent Manager**: Enforces patient privacy by requiring explicit consent or an active referral for data sharing.
4.  **Chained Audit Log**: A tamper-evident ledger that records all cross-facility data access, including emergency break-glass events.
5.  **Audit Review**: A specialized interface for Super Admins to monitor and validate the legitimacy of emergency access events.
6.  **AI Decision Support**: To improve clinical decision quality within the inter-hospital context, an AI-assisted triage and referral recommendation layer was added. This identifies the optimal destination facility based on clinical urgency and specialty availability.

## Viva sequence diagrams

### 1) Register patient at Hospital A

```mermaid
sequenceDiagram
    actor Clerk as Receptionist/Doctor
    participant API as POST /api/v1/patients
    participant View as patient_views.patient_create
    participant Patient as Patient
    participant Allergy as Allergy
    participant Audit as AuditLog
    participant Backfill as manage.py backfill_global_patients
    participant GP as GlobalPatient
    participant FP as FacilityPatient

    Clerk->>API: POST patient payload
    API->>View: patient_create(request)
    View->>Patient: create()
    opt allergies supplied
        View->>Allergy: create()
    end
    View->>Audit: CREATE_PATIENT
    View-->>Clerk: 201 {"data": PatientSerializer(patient).data}
    Backfill->>GP: get_or_create by Ghana Health ID
    Backfill->>FP: create facility link
```

**Path:** `POST /api/v1/patients` → `patient_views.patient_create`
**Models:** `Patient`, `Allergy`, `GlobalPatient`, `FacilityPatient`, `AuditLog`
**Audit:** `CREATE_PATIENT`
**Response:** `{"data": PatientSerializer(patient).data}`

### 2) Refer patient with consent

```mermaid
sequenceDiagram
    actor Doctor as Hospital A doctor
    participant ConsentAPI as POST /api/v1/consents
    participant ConsentView as consent_views.consent_grant
    participant Consent as Consent
    participant ConsentAudit as AuditLog
    participant ReferralAPI as POST /api/v1/referrals
    participant ReferralView as referral_views.referral_create
    participant GP as GlobalPatient
    participant Hospital as Hospital
    participant Referral as Referral
    participant ReferralAudit as AuditLog

    Doctor->>ConsentAPI: grant consent payload
    ConsentAPI->>ConsentView: consent_grant(request)
    ConsentView->>Consent: create()
    ConsentView->>ConsentAudit: CREATE resource_type=consent
    ConsentView-->>Doctor: 201 ConsentSerializer(consent).data

    Doctor->>ReferralAPI: create referral payload
    ReferralAPI->>ReferralView: referral_create(request)
    ReferralView->>GP: get(id=global_patient_id)
    ReferralView->>Hospital: get(id=to_facility_id)
    ReferralView->>Consent: optional active consent lookup
    ReferralView->>Referral: create()
    ReferralView->>ReferralAudit: CREATE resource_type=referral
    ReferralView-->>Doctor: 201 {"data": ReferralSerializer(ref).data}
```

**Path:** `POST /api/v1/consents` then `POST /api/v1/referrals`
**Models:** `Consent`, `GlobalPatient`, `Hospital`, `Referral`, `AuditLog`
**Audit:** `CREATE` on consent, `CREATE` on referral
**Response:** consent serializer, then referral serializer

### 3) Hospital B doctor reads shared records

```mermaid
sequenceDiagram
    actor DoctorB as Hospital B doctor
    participant API as GET /api/v1/cross-facility-records/{gpid}
    participant View as global_patient_views.cross_facility_records
    participant ACL as can_access_cross_facility()
    participant Consent as Consent
    participant Referral as Referral
    participant BG as BreakGlassLog
    participant Shared as SharedRecordAccess
    participant Audit as AuditLog
    participant MR as MedicalRecord

    DoctorB->>API: GET cross-facility records
    API->>View: cross_facility_records(request, gpid)
    View->>ACL: check consent/referral/break-glass
    ACL-->>View: allowed + scope
    View->>Shared: create()
    View->>Audit: VIEW_CROSS_FACILITY_RECORD
    alt scope == FULL_RECORD
        View->>MR: fetch linked MedicalRecord rows
    end
    View-->>DoctorB: 200 demographics + facilities + records
```

**Path:** `GET /api/v1/cross-facility-records/<global_patient_id>/`
**Models:** `Consent`, `Referral`, `BreakGlassLog`, `SharedRecordAccess`, `MedicalRecord`, `AuditLog`
**Audit:** `VIEW_CROSS_FACILITY_RECORD`
**Response:** `demographics`, `scope`, `facilities`, `records`, `read_only`, `expires_at`

### 4) Break-glass emergency access

```mermaid
sequenceDiagram
    actor Doctor as Hospital doctor
    participant API as POST /api/v1/break-glass
    participant View as break_glass_views.break_glass_create
    participant GP as GlobalPatient
    participant BG as BreakGlassLog
    participant Audit as AuditLog
    participant Notify as Email notification

    Doctor->>API: POST reason_code + reason
    API->>View: break_glass_create(request)
    View->>GP: get(id=global_patient_id)
    View->>BG: create(expires_at=now+window)
    View->>Audit: EMERGENCY_ACCESS with chain_hash
    View->>Notify: send_mail()
    View-->>Doctor: 201 BreakGlassLogSerializer(log).data
```

**Path:** `POST /api/v1/break-glass`
**Models:** `GlobalPatient`, `BreakGlassLog`, `AuditLog`
**Audit:** `EMERGENCY_ACCESS` with chain hash
**Response:** `BreakGlassLogSerializer(log).data`

### 5) Revoke consent

```mermaid
sequenceDiagram
    actor Admin as Granting facility or super admin
    participant API as PATCH /api/v1/consents/{uuid}
    participant View as consent_views.consent_revoke
    participant Service as consent_service.revoke_consent
    participant Consent as Consent
    participant Audit as AuditLog

    Admin->>API: PATCH withdrawal_reason
    API->>View: consent_revoke(request, pk)
    View->>Service: revoke_consent(request, pk)
    Service->>Consent: withdraw()
    Service->>Audit: CONSENT_WITHDRAWN
    Service-->>View: updated Consent
    View-->>Admin: 200 ConsentSerializer(consent).data
```

**Path:** `PATCH /api/v1/consents/<uuid>`
**Models:** `Consent`, `AuditLog`
**Audit:** `CONSENT_WITHDRAWN`
**Response:** updated consent serializer

### 6) Super admin reviews audit chain

```mermaid
sequenceDiagram
    actor Super as Super admin
    participant API as GET /api/v1/superadmin/audit-chain-integrity
    participant View as superadmin_views.audit_chain_integrity_status
    participant Service as compute_audit_chain_status()
    participant Log as AuditLog

    Super->>API: GET audit chain status
    API->>View: audit_chain_integrity_status(request)
    View->>Service: validate chain_hash + signature
    Service->>Log: iterate ordered AuditLog rows
    Service-->>View: {"status","last_checked_at","message"}
    View-->>Super: 200 {"data": ...}
```

**Path:** `GET /api/v1/superadmin/audit-chain-integrity`
**Models:** `AuditLog`
**Audit:** no new row; validation only
**Response:** `{"data": {"status", "last_checked_at", "message"}}`
