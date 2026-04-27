# Getting Started with MedSync EMR

**Welcome to MedSync EMR!** This guide will help you get started with the system.

---

## 🎯 What is MedSync EMR?

MedSync is a **centralized, multi-hospital Electronic Medical Records system** for Ghana's inter-hospital network.

**Key Features:**
- ✅ Role-based access control (Super Admin, Hospital Admin, Doctor, Nurse, Lab Tech, Receptionist)
- ✅ Multi-tenant architecture (each hospital has isolated data)
- ✅ Cross-facility record sharing (with consent and referrals)
- ✅ Clinical alerts and safety features (MEWS, NEWS2 scoring)
- ✅ AI/ML analytics (in development for clinical deployment)
- ✅ Secure authentication (JWT + TOTP MFA)
- ✅ Offline support (PWA with IndexedDB)

---

## 🚀 Quick Navigation

### 📖 I want to understand the system
→ Start with **[docs/ARCHITECTURE.md](ARCHITECTURE.md)** (15 minutes)

### 💻 I want to set up locally
→ Follow **[docs/DEPLOYMENT.md](DEPLOYMENT.md)** and the README in each folder:
- Backend: `medsync-backend/README.md`
- Frontend: `medsync-frontend/README.md`

### 🔍 I'm looking for a specific feature
→ Browse **[docs/INDEX.md](INDEX.md)** or search the relevant category:
- [Deployment/](Deployment/) — How to deploy
- [Security/](Security/) — Authentication & compliance
- [AI_ML/](AI_ML/) — Analytics features
- [Features/](Features/) — User permissions & workflows

### 🐛 Something is broken
→ Check **[docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

---

## 📚 Documentation Organization

All documentation is organized in the `docs/` folder:

```
docs/
├── QUICK_START.md ← Quick reference by role
├── INDEX.md ← Master documentation index
├── GETTING_STARTED.md ← This file
│
├── Core Docs (read first)
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── API_REFERENCE.md
│   ├── TROUBLESHOOTING.md
│   └── ... (5 more)
│
├── Deployment/ (4 deployment guides)
├── Security/ (8 security docs)
├── AI_ML/ (4 AI/ML docs)
├── Features/ (6 feature docs)
├── Architecture/ (1 design doc)
└── Quality/ (2 quality audit docs)
```

**Total:** 33+ documentation files, fully organized and current

---

## 👤 Choose Your Starting Path

### 👨‍💻 **New Developer**

**Time:** 1.5 hours

1. **Read System Overview** (15 min)
   - Open `docs/ARCHITECTURE.md`
   - Understand multi-tenancy, authentication, API structure

2. **Set Up Locally** (20 min)
   - Backend: Follow `medsync-backend/README.md`
   - Frontend: Follow `medsync-frontend/README.md`
   - Start both servers with: `python manage.py runserver` and `npm run dev`

3. **Explore the API** (30 min)
   - Read `docs/API_REFERENCE.md`
   - Test endpoints with: `curl http://localhost:8000/api/v1/health`
   - Try login with test credentials from backend README

4. **Understand Permissions** (15 min)
   - Read `docs/Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md`
   - This explains what each user role can do

5. **Start Coding**
   - Backend: Edit files in `medsync-backend/api/`
   - Frontend: Edit files in `medsync-frontend/src/`
   - Follow code patterns in existing files

---

### 🔧 **DevOps / Infrastructure Engineer**

**Time:** 45 minutes

1. **Deployment Guide** (20 min)
   - Read `docs/DEPLOYMENT.md` (primary reference)
   - Understand Railway setup for web service

2. **Critical Services** (10 min)
   - Read `docs/Deployment/CELERY_WORKER_DEPLOYMENT_DOCUMENTATION.md`
   - ⚠️ Celery workers are MANDATORY (not optional)
   - Set up two additional Railway services: worker and beat scheduler

3. **Database Setup** (5 min)
   - Read `docs/Deployment/NEON_REGION_SELECTION_FIX.md`
   - Use **Africa/Cape Town** region (aws-af-south-1) for Ghana deployment

4. **Monitoring** (10 min)
   - Read `docs/Monitoring_And_Alerting.md`
   - Set up health check alerts

---

### 🔐 **Security / Compliance Officer**

**Time:** 30 minutes

1. **Security Audit** (10 min)
   - Read `docs/Security/SECURITY_AUDIT_SUMMARY.md`

2. **Authentication Security** (5 min)
   - Read `docs/Security/JWT_ALGORITHM_SECURITY_FIX.md`
   - Algorithm: HS256 (explicitly configured, secure for internal use)

3. **MFA Requirements** (5 min)
   - Read `docs/Security/MFA_MANDATORY_REQUIREMENT_CORRECTION.md`
   - ⚠️ MFA is MANDATORY for all clinical staff (no exceptions in production)

4. **Data Protection** (10 min)
   - Read `docs/BACKUP_STRATEGY.md`
   - Understand backup procedures and compliance requirements

---

### 🏥 **Clinical Administrator / Hospital Admin**

**Time:** 1 hour

1. **System Overview** (15 min)
   - Read `docs/ARCHITECTURE.md` sections on overview and multi-tenancy

2. **User Roles & Permissions** (15 min)
   - Read `docs/Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md`
   - Understand what each role can do

3. **User Management** (15 min)
   - Read `docs/ADMIN_RUNBOOK.md`
   - Learn how to add users, manage staff, view audit logs

4. **Operations & Monitoring** (15 min)
   - Read `docs/Monitoring_And_Alerting.md`
   - Understand system health and alerts

---

### 🤖 **AI / ML Engineer**

**Time:** 30 minutes

1. **AI Status** (10 min)
   - Read `docs/AI_ML/AI_ML_STATUS_REPORT.md`
   - Current state: infrastructure ready, models in development

2. **Deployment Readiness** (5 min)
   - Read `docs/AI_ML/AI_ML_PRODUCTION_READINESS_CORRECTION.md`
   - Understand infrastructure vs clinical readiness

3. **Clinical Deployment Plan** (15 min)
   - Read `docs/AI_ML/AI_ML_CLINICAL_DEPLOYMENT_ROADMAP.md`
   - 4-phase plan, 9+ months to clinical readiness

---

## 🔑 Key Information

### Environment Setup
```bash
# Backend
cd medsync-backend
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On macOS/Linux: source .venv/bin/activate
pip install -r requirements-local.txt
python manage.py migrate
python manage.py setup_dev
python manage.py runserver

# Frontend
cd medsync-frontend
npm install
npm run dev

# Visit:
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/api/schema/swagger/
```

### Test Credentials (after setup_dev)
```
Super Admin:        c / Admin123!@#
Doctor:             doctor@medsync.gh / Doctor123!
Hospital Admin:     hospital_admin@medsync.gh / HospitalAdmin123!
Nurse:              nurse@medsync.gh / Nurse123!@#
Lab Technician:     lab_technician@medsync.gh / LabTech123!@#
Receptionist:       receptionist@medsync.gh / Receptionist123!@#
```

### Important Commands
```bash
# Backend
python manage.py runserver              # Start dev server
python -m pytest api/tests/ -v          # Run all tests
python manage.py migrate                # Apply migrations
python manage.py setup_dev              # Reset and seed dev data

# Frontend
npm run dev                  # Start dev server
npm run test               # Run tests
npm run build              # Production build
npm run lint               # Check code style
```

### Key Ports
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/schema/swagger/
- PostgreSQL: localhost:5432 (production only)

---

## 🎯 Common Tasks

### "I need to add a new user"
→ See `docs/ADMIN_RUNBOOK.md` → User Management section

### "I need to understand the API"
→ Visit: http://localhost:8000/api/schema/swagger/ (when running)

### "Something isn't working"
→ Check `docs/TROUBLESHOOTING.md` → Your issue might be there

### "I need to deploy to production"
→ Follow `docs/DEPLOYMENT.md` carefully (especially Celery setup)

### "I need to understand cross-hospital access"
→ Read `docs/Architecture/Access_Governance.md`

### "I need to know about clinical safety features"
→ Read `docs/Features/SAFETY_IMPLEMENTATION_REFERENCE.md`

---

## 📋 Important Reminders

✅ **Always read the backend README** — `medsync-backend/README.md` for setup details

✅ **Always read the frontend README** — `medsync-frontend/README.md` for setup details

✅ **Check TROUBLESHOOTING first** — `docs/TROUBLESHOOTING.md` for common issues

✅ **MFA is mandatory** — All clinical staff must use MFA (no exceptions in production)

✅ **Celery is critical** — Deploy both worker and beat scheduler (not optional)

✅ **Use Africa/Cape Town** — For database region when deploying to Ghana

✅ **Documentation is current** — Last updated April 2026, includes all Phase 2-8 features

---

## 📞 Getting Help

| Question | Answer |
|----------|--------|
| How do I start? | Read this guide based on your role |
| Where's the API docs? | `docs/API_REFERENCE.md` or visit Swagger UI |
| Something broken? | Check `docs/TROUBLESHOOTING.md` |
| Need deployment help? | Read `docs/DEPLOYMENT.md` |
| Need code examples? | Check existing files in `medsync-backend/api/` and `medsync-frontend/src/` |
| Need to understand permissions? | Read `docs/Features/ROLE_BASED_USERS_PERMISSIONS_BY_MODULE.md` |

---

## 🎓 Learning Resources

### For Understanding the System
- `docs/ARCHITECTURE.md` — Complete system design (20 min read)
- `docs/Architecture/Multi_Tenancy_Architecture.md` — Hospital scoping model
- `docs/API_REFERENCE.md` — All endpoints (reference)

### For Coding
- `medsync-backend/README.md` — Backend setup and patterns
- `medsync-frontend/README.md` — Frontend setup and patterns
- `docs/Features/` folder — Feature-specific documentation

### For Operations
- `docs/DEPLOYMENT.md` — Production deployment
- `docs/ADMIN_RUNBOOK.md` — Operational tasks
- `docs/Monitoring_And_Alerting.md` — System health

### For Security
- `docs/Security/` folder — All security-related docs
- `docs/BACKUP_STRATEGY.md` — Data protection

---

## 🚀 Next Steps

1. **Choose your role** above and follow your starting path
2. **Set up your environment** (local dev or deployment)
3. **Read relevant documentation** for your task
4. **Start contributing!**

---

**Last Updated:** April 20, 2026  
**Status:** ✅ Current (includes all Phase 2-8 features)  

**👉 Next:** [docs/QUICK_START.md](QUICK_START.md) — Quick reference by role
