# 📚 MedSync EMR Documentation

Welcome to the MedSync documentation! This is your central hub for all system information.

---

## 🚀 Quick Start

**Choose your role to get started:**

| Role | Time | Start Here |
|------|------|-----------|
| **New Developer** | 1.5 hours | [GETTING_STARTED.md](GETTING_STARTED.md) → Choose "New Developer" |
| **DevOps/Infrastructure** | 45 min | [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Security/Compliance** | 30 min | [Security/SECURITY_AUDIT_SUMMARY.md](Security/SECURITY_AUDIT_SUMMARY.md) |
| **Clinical Leaders** | 1 hour | [ARCHITECTURE.md](ARCHITECTURE.md) → Overview section |
| **AI/LLM Integration** | 5 min | [INDEX.md](INDEX.md#ai--discharge-summary) |
| **Quick Reference** | ⏱️ | [QUICK_START.md](QUICK_START.md) |
| **Looking for something?** | 🔍 | [INDEX.md](INDEX.md) |

---

## 📖 Three Ways to Navigate

### 1. **By Role** (Recommended for New People)
→ [QUICK_START.md](QUICK_START.md) — Choose your role, get recommended docs

### 2. **By Topic** (Recommended for Specific Info)
→ [INDEX.md](INDEX.md) — Search by category or topic

### 3. **By Category** (Recommended for Browsing)
- [Deployment/](Deployment/) — How to deploy
- [Security/](Security/) — Authentication, compliance, audits
- [INDEX.md#ai](INDEX.md#ai--discharge-summary) — AI / LLM discharge summary
- [Features/](Features/) — User permissions and workflows
- [Architecture/](Architecture/) — System design
- [Quality/](Quality/) — Documentation and audit reports

---

## ⭐ Essential Files (Read These First)

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — Understand the system design (15 min)
2. **[DEPLOYMENT.md](DEPLOYMENT.md)** — Learn how to deploy (20 min)
3. **[API_REFERENCE.md](API_REFERENCE.md)** — Find available endpoints (reference)

---

## 🎯 By Task

**Setting up locally?**
→ [GETTING_STARTED.md](GETTING_STARTED.md)

**Deploying to production?**
→ [DEPLOYMENT.md](DEPLOYMENT.md)

**Need security info?**
→ [Security/SECURITY_AUDIT_SUMMARY.md](Security/SECURITY_AUDIT_SUMMARY.md)

**Troubleshooting?**
→ [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Managing users?**
→ [ADMIN_RUNBOOK.md](ADMIN_RUNBOOK.md)

**Understanding permissions?**
→ [Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md](Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md)

**API documentation?**
→ [API_REFERENCE.md](API_REFERENCE.md)

**AI discharge summary?**
→ [INDEX.md](INDEX.md#ai--discharge-summary)

**Backup and recovery?**
→ [BACKUP_STRATEGY.md](BACKUP_STRATEGY.md)

---

## 📁 Documentation Structure

```
docs/
├── README.md ← You are here
├── INDEX.md ..................... Master index (all files listed)
├── QUICK_START.md .............. Role-based quick start
├── GETTING_STARTED.md ......... Comprehensive setup guide
│
├── Core Docs
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── DEPLOY_RUNBOOK.md
│   ├── GO_NO_GO_CHECKLIST.md
│   ├── API_REFERENCE.md
│   ├── TROUBLESHOOTING.md
│   ├── ADMIN_RUNBOOK.md
│   ├── BACKUP_STRATEGY.md
│   └── OPENAPI_SETUP.md
│
├── Deployment/ (1 file)
│   └── NEON_REGION_SELECTION_FIX.md
│
├── Security/ (8 files)
│   ├── SECURITY_AUDIT_SUMMARY.md
│   ├── JWT_ALGORITHM_SECURITY_FIX.md
│   ├── MFA_MANDATORY_REQUIREMENT_CORRECTION.md
│   └── ... (5 more)
│
├── Features/ (6 files)
│   ├── ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md
│   ├── QUICK_REFERENCE_STATE_MACHINES.md
│   └── ... (4 more)
│
└── Architecture/ (empty — see ARCHITECTURE.md in root)
```

**Total:** 35 documentation files organized into 6 categories

---

## ⚠️ Important Information

### 🔴 Critical
- **MFA is MANDATORY** for all clinical staff — [Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md](Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md)
- **AI discharge summary requires LLM_MODE=bedrock** — see [INDEX.md](INDEX.md#ai--discharge-summary); mock mode is blocked in production
- **Complete Tier 1 checklist** before any real patient data — [GO_NO_GO_CHECKLIST.md](GO_NO_GO_CHECKLIST.md)

### 🟡 Important
- **Database region:** Use Africa/Cape Town for Ghana deployment — [Deployment/NEON_REGION_SELECTION_FIX.md](Deployment/NEON_REGION_SELECTION_FIX.md)
- **JWT algorithm:** HS256 (explicitly configured, secure) — [Security/JWT_ALGORITHM_SECURITY_FIX.md](Security/JWT_ALGORITHM_SECURITY_FIX.md)
- **Documentation updated:** June 2026

---

## 📊 Documentation Stats

| Metric | Value |
|--------|-------|
| Total Files | 35 |
| Categories | 6 |
| Total Size | ~0.56 MB |
| Last Updated | April 2026 |
| Status | ✅ Current |
| Audit Ready | ✅ Yes |

---

## 🎯 Getting Help

| Need | Solution |
|------|----------|
| System overview | Read [ARCHITECTURE.md](ARCHITECTURE.md) |
| Setup guide | Follow [GETTING_STARTED.md](GETTING_STARTED.md) |
| Quick reference | Use [QUICK_START.md](QUICK_START.md) |
| Find something | Browse [INDEX.md](INDEX.md) |
| Deployment help | Read [DEPLOYMENT.md](DEPLOYMENT.md) |
| Security info | Check [Security/](Security/) folder |
| Troubleshooting | See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| API docs | View [API_REFERENCE.md](API_REFERENCE.md) |

---

## 🚀 Next Steps

1. **New to MedSync?** → Read [GETTING_STARTED.md](GETTING_STARTED.md)
2. **Know your role?** → Use [QUICK_START.md](QUICK_START.md)
3. **Looking for something?** → Browse [INDEX.md](INDEX.md)
4. **Need to deploy?** → Follow [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📚 Complete File Index

See [INDEX.md](INDEX.md) for a complete list of all files with descriptions.

---

**Last Updated:** April 2026  
**Status:** ✅ Current and Complete  
**Questions?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or [INDEX.md](INDEX.md)

👉 **Start with:** [GETTING_STARTED.md](GETTING_STARTED.md)
