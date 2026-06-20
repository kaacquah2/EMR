# MedSync EMR: Student Portfolio & Project Documentation

Welcome to the MedSync EMR project documentation index. This documentation is structured as a comprehensive software engineering student portfolio and project report, detailing the requirements, architectural decisions, security controls, and operational workflows of the centralized inter-hospital EMR system for Ghana.

---

## 📚 Table of Contents

### [Chapter 0: Background Study & Literature Review](0_background_study.md)
*Grounds the project title in academic literature. Decomposes "Secure Centralized EMR for Inter-Hospital Access" into four gradable pillars and maps each to the relevant standards (HIPAA, NDPA 2012, NIST 800-63B, IHE PIX/PDQ/BPPC/XCA, HL7 FHIR R4). Explains the hub-and-spoke MPI architecture pattern and its fit for Ghana's tiered health system. Includes a reference list and a summary table mapping title claims to implementation.*

### [Chapter 1: Project Overview & Requirements](1_project_overview.md)
*Introduces the MedSync system, the fragmented clinical data problem in Ghana's healthcare tiers, detailed functional requirements, regulatory constraints (Ghana NDPA 2012 / HIPAA), and the role-based dashboard matrix.*

### [Chapter 2: System Architecture & Multi-Tenancy Design](2_system_architecture.md)
*Covers the hub-and-spoke architectural paradigm (Central Global Hub, Facility Spoke Layer, and HIE integration layer), database-level query isolation using centralised scoping helpers (`api/utils.py`), and Super Admin X-View-As-Hospital projection mechanisms. Also explains why the design is defensibly called "centralized" (central MPI + consent governance) while using per-facility clinical data isolation.*

### [Chapter 3: Database Design & Cryptographic Protection](3_database_design.md)
*Details the relational schemas for the `core`, `patients`, `records`, and `interop` models, the legal retention duration calculator matching Ghana Ministry of Health guidelines, and the field-level encryption (AES-256) protecting patient PHI columns.*

### [Chapter 4: Security & Compliance Implementation](4_security_and_compliance.md)
*Explains authentication security, multi-factor auth pathways, account lockout prevention, trusted device fingerprint matching, step-up session OTP flows, and the tamper-evident hash-chain audit log with HMAC signatures.*

### [Chapter 5: Interoperability & Cross-Facility Workflows](5_interoperability_and_workflows.md)
*Examines cross-hospital patient identity matching (GPID), consent-gate summary/full-record scopes, the referral state machine, the emergency Break-Glass bypass workflow, and local data residency locks.*

### [Chapter 6: Developer Setup & Operations Manual](6_developer_manual.md)
*Walks through backend and frontend local installations, environment configuration files, database migration and seed commands, and executing backend (Pytest), frontend (Vitest), and end-to-end (Playwright) test suites.*

### [Chapter 7: Project Evaluation, Limitations & Future Roadmap](7_evaluation_and_future_work.md)
*Reflects on the completed engineering strengths, details technical concurrency and race conditions solved, highlights current system mock boundaries, and diagrams the future health network integrations.*

---

## 🔍 How to Read This Documentation
- **For Evaluators/Graders:** Start with [Chapter 1](1_project_overview.md) and [Chapter 2](2_system_architecture.md) to understand the project objectives, architecture, and core data-isolation model.
- **For Security Reviewers:** Go directly to [Chapter 4](4_security_and_compliance.md) to review the cryptographic details of the tamper-evident log chain and field-level encryption.
- **For Developers/Reviewers:** Jump to [Chapter 6](6_developer_manual.md) to set up and verify the local environments and execute tests.
