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
