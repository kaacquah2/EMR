# Deployment Runbook Update — April 2026

**Date:** April 19, 2026  
**Status:** ✅ COMPLETE  
**File Updated:** `docs/DEPLOYMENT.md`

---

## Overview

The DEPLOYMENT.md runbook was **3+ months outdated** (last updated December 2024). Since then, MedSync added major features that required deployment steps, environment variables, and health checks:

1. ✅ WebAuthn/Passkey authentication endpoints
2. ✅ AI module with 5 ML models and Celery async jobs
3. ✅ Push notification infrastructure (VAPID keys)
4. ✅ Phase 2-5 features (cross-facility access, break-glass, referrals, etc.)

**This runbook update adds comprehensive documentation for all new features.**

---

## What Was Added to DEPLOYMENT.md

### 1. Updated Header & Critical Warning

```markdown
**Last Updated:** April 2026  
Status: Production-Ready

> ⚠️ **CRITICAL:** This runbook was updated April 2026 to document WebAuthn/passkey endpoints, 
> AI module infrastructure, push notifications (VAPID), Celery async tasks, and all Phase 2-5 
> features. Verify all environment variables before deployment.
```

### 2. New Environment Variables Sections

#### Push Notifications (Web Push / VAPID) — NEW

```bash
# Generate VAPID keys using web-push CLI
npm install -g web-push
web-push generate-vapid-keys

# Set in production:
VAPID_PUBLIC_KEY=<public-key-from-web-push>
VAPID_PRIVATE_KEY=<private-key-from-web-push>
VAPID_CLAIM_EMAIL=mailto:admin@medsync.app
```

**Why it matters:** Without VAPID keys, push notifications won't send. This is critical for appointment reminders, lab results, and referral notifications.

#### Async Task Queue (Celery) — NEW

```bash
# Requires Redis broker for background jobs
CELERY_BROKER_URL=redis://:password@redis.railway.app:port/0
CELERY_RESULT_BACKEND=redis://:password@redis.railway.app:port/0
```

**Why it matters:** Background jobs (no-show marking, AI predictions, report generation, appointment reminders) run async. Without Redis/Celery, these fail silently.

#### AI Module (ML Models & Governance) — NEW

```bash
AI_GOVERNANCE_ENABLED=True          # Enable AI feature toggle
DISABLE_AI_FEATURES=False            # Emergency shutdown
AI_CONFIDENCE_THRESHOLD=0.5          # Only return predictions ≥50% confidence
MEDSYNC_AI_MODELS_DIR=/path/to/models
```

**Why it matters:** AI infrastructure is production-ready (for testing/UX), but models are placeholder (development-stage). Misunderstanding this risks deploying placeholder scores to real clinical workflows.

#### MFA Configuration — CLARIFIED

```bash
# MFA is MANDATORY for all clinical roles
# DEV_BYPASS_MFA only for local development (NEVER in production)
DEV_BYPASS_MFA=False
```

**Why it matters:** MFA was previously shown as optional. Documentation now clearly states it's mandatory with emergency bypass noted.

#### Audit & Security — NEW

```bash
# HMAC signing key for audit log chain signatures
AUDIT_LOG_SIGNING_KEY=<random-64-char-key>

# Break-glass emergency access settings
BREAK_GLASS_WINDOW_MINUTES=15
BREAK_GLASS_NOTIFY_EMAILS=admin@hospital.gh,security@hospital.gh
```

---

### 3. Comprehensive Post-Deployment Health Checks — MAJOR EXPANSION

Added 8 comprehensive health check sections with curl commands:

#### a. **API Core Health**
```bash
curl -s https://api.medsync.app/api/v1/health | jq .
# Verifies: database, redis, overall system status
```

#### b. **WebAuthn/Passkey Endpoints**
```bash
curl https://api.medsync.app/api/v1/auth/passkey/registration-options \
  -H "Authorization: Bearer <access_token>" | jq .
```

#### c. **AI Module Health** ✨ NEW
```bash
curl https://api.medsync.app/api/v1/ai/health \
  -H "Authorization: Bearer <access_token>" | jq .
# Expected: "model_status": "development-stage"
```

#### d. **Push Notifications (VAPID)** ✨ NEW
```bash
curl https://api.medsync.app/api/v1/push/vapid-public-key | jq .
# Must return non-empty public key
```

#### e. **Celery Async Tasks** ✨ NEW
```bash
redis-cli -h <redis-host> -p <redis-port> PING
# Expected: PONG
```

#### f. **Database & Migrations**
```bash
psql postgresql://user:pass@neon.tech/medsync_prod -c "\dt"
# Verify all tables exist including new ones: api_aimodel, webpush_subscription
```

#### g. **Audit Logging**
```bash
psql -d medsync_prod -c "SELECT COUNT(*) FROM core_auditlog WHERE created_at > NOW() - INTERVAL '1 hour';"
# Expected: >0 recent entries
```

### 4. Updated Validation Checklists

**Immediately After Deployment:**
- ✅ WebAuthn endpoints respond
- ✅ **AI endpoints respond (even if placeholder)** — ✨ NEW
- ✅ **Push notification VAPID key available** — ✨ NEW
- ✅ **Celery worker running** — ✨ NEW

**Within 24 Hours:**
- ✅ **Push notifications sending** — ✨ NEW
- ✅ **AI model predictions generating** — ✨ NEW
- ✅ **Celery tasks executing** — ✨ NEW
- ✅ **Redis/Celery broker stable** — ✨ NEW

**Weekly:**
- ✅ **AI endpoints responding <5s latency** — ✨ NEW
- ✅ **Push subscription management working** — ✨ NEW
- ✅ **Celery task queue not backed up** — ✨ NEW

### 5. New Troubleshooting Sections

#### "AI Endpoints Return 500 or 'Model Not Found'"
```
Cause: AI models not loaded or missing
Solution: Verify DISABLE_AI_FEATURES=False, check model files exist, check logs
Note: Placeholder models normal in development-stage
```

#### "Push Notifications Not Sending"
```
Cause: VAPID keys missing or Redis not connected
Solution: Verify VAPID keys match, check Redis, test subscription storage
```

#### "Celery Tasks Not Executing"
```
Cause: Redis down, Celery worker not running, or queue backed up
Solution: Check Redis PING, check worker status, monitor queue depth
```

#### "WebAuthn/Passkey Endpoints 404"
```
Cause: WEBAUTHN_ENABLED=False or migration not run
Solution: Verify WEBAUTHN_ENABLED=True, run migrations
```

### 6. Updated Maintenance Tasks

**Daily:**
- Monitor API error rates
- **Check Celery queue depth** — ✨ NEW
- **Monitor AI endpoint response times** — ✨ NEW

**Weekly:**
- Review database size
- **Verify Celery beat scheduler running** — ✨ NEW
- **Confirm push notification queue emptying** — ✨ NEW
- **Check AI model inference latency** — ✨ NEW

**Monthly:**
- Review dependencies
- **Analyze AI endpoint usage** — ✨ NEW
- **Review Celery task execution metrics** — ✨ NEW
- **Confirm WebAuthn adoption** — ✨ NEW

**Quarterly:**
- Load testing
- **AI model retraining evaluation** — ✨ NEW
- **Celery infrastructure scale testing** — ✨ NEW

### 7. Enhanced Security Checklist

Added new production security items:
- ✅ **VAPID keys generated and stored securely**
- ✅ **DEV_BYPASS_MFA=False in production**
- ✅ **AI_CONFIDENCE_THRESHOLD set appropriately**
- ✅ **Celery Redis broker password strong and encrypted**
- ✅ **AI models identified as development-stage (not clinical-ready)**

### 8. Updated "Next Steps After Deployment"

Now includes:
- ✅ WebAuthn/passkey setup instructions
- ✅ AI infrastructure limitations & clinical deployment roadmap
- ✅ Push notification subscription process
- ✅ Celery task monitoring
- ✅ Links to supporting documentation

---

## Key Highlights

### ✨ What's New in the Runbook

| Feature | What's Documented | Why It Matters |
|---------|-------------------|----------------|
| **WebAuthn/Passkey** | Endpoints, registration flow, health checks | Clinicians can authenticate with biometric/hardware keys |
| **AI Module** | VAPID setup, model status, clinical deployment roadmap | Infrastructure ready for testing; models require 9+ months for clinical use |
| **Push Notifications** | VAPID key generation, subscription management, troubleshooting | Appointment reminders, lab results, referral notifications require this |
| **Celery/Redis** | Broker configuration, task monitoring, queue health checks | Background jobs (no-show marking, AI predictions, reports) depend on this |
| **MFA** | MANDATORY requirement, DEV_BYPASS_MFA exception | Clarifies MFA is not optional in production |

### 📋 Health Check Commands Added

8 comprehensive health checks with curl/psql commands:
1. ✅ Core API health
2. ✅ WebAuthn endpoints
3. ✅ AI module health
4. ✅ Push notification VAPID key
5. ✅ Celery/Redis connection
6. ✅ Database migrations
7. ✅ Audit logging
8. ✅ SSL certificate

### 🔧 Troubleshooting Added

4 new troubleshooting sections for:
- AI endpoints returning errors
- Push notifications not sending
- Celery tasks not executing
- WebAuthn endpoints missing

### 📅 Maintenance Updated

All daily/weekly/monthly/quarterly tasks now include new feature monitoring (Celery, AI, Push notifications, WebAuthn).

---

## Important Notes for Deployment

### 1. VAPID Key Generation Required Before Deployment

```bash
# MUST be done before setting VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY
npm install -g web-push
web-push generate-vapid-keys
```

If VAPID keys are not set, push notifications will silently fail.

### 2. Redis Required for Production

Celery background jobs require Redis. Without it:
- No-show marking won't run every 15 minutes
- AI model training jobs will queue indefinitely
- Appointment reminders won't send
- Report generation will fail

### 3. AI Models Are Placeholder

Current AI models are **development-stage**, not clinical-ready:
- Models use synthetic/test data
- No validation against real patient outcomes
- **DO NOT DEPLOY** to clinical workflows without 9+ months of:
  - Real data collection
  - Model retraining and validation
  - Bias assessment
  - Regulatory/compliance review

See `AI_ML_PRODUCTION_READINESS_CORRECTION.md` for clinical deployment roadmap.

### 4. MFA Is Mandatory

- All clinical roles (doctors, nurses, lab techs, admins) **MUST** enable MFA
- No optional path in production
- `DEV_BYPASS_MFA=True` only for local development
- Implementation enforces 403 Forbidden if MFA not enabled

### 5. Verify All Environment Variables

Before deploying, verify:
- [ ] All VAPID keys set correctly
- [ ] CELERY_BROKER_URL and CELERY_RESULT_BACKEND point to Redis
- [ ] AI_GOVERNANCE_ENABLED=True (or False if disabling AI)
- [ ] DEV_BYPASS_MFA=False (never True in production)
- [ ] AUDIT_LOG_SIGNING_KEY is cryptographically random

---

## Files Referenced in Updated Runbook

| Document | Purpose |
|----------|---------|
| `docs/DEPLOYMENT.md` | **This runbook** (now updated for April 2026) |
| `docs/ARCHITECTURE.md` | System architecture, authentication, components |
| `docs/AI_ML_PRODUCTION_READINESS_CORRECTION.md` | AI infrastructure vs clinical readiness distinction |
| `docs/AI_ML_CLINICAL_DEPLOYMENT_ROADMAP.md` | 9+ month phased plan for clinical AI deployment |
| `docs/MFA_MANDATORY_REQUIREMENT_CORRECTION.md` | MFA mandatory requirement clarification |
| `docs/JWT_ALGORITHM_SECURITY_FIX.md` | JWT security model and algorithm choice |
| `medsync-backend/medsync_backend/settings.py` | Configuration (lines 488-491 VAPID, 617-653 Celery) |

---

## Status

✅ **DEPLOYMENT.md UPDATED AND READY FOR USE**

- Last Updated: April 19, 2026
- Covers all features through Phase 8.2
- Includes health checks for WebAuthn, AI, Push Notifications, Celery
- Comprehensive troubleshooting for new features
- Security checklist updated for new components
- Next review: After next major feature release

---

## Action Items for Deployment Teams

1. ✅ Generate and store VAPID keys before deployment
2. ✅ Verify Redis/Celery broker is available
3. ✅ Set all new environment variables from updated runbook
4. ✅ Run comprehensive health checks after deployment
5. ✅ Read AI deployment roadmap if planning clinical AI use
6. ✅ Train staff on WebAuthn/passkey setup
7. ✅ Monitor Celery queue and AI endpoints for first 48 hours
8. ✅ Verify push notifications sending for appointment reminders

---

**Document Version:** v1.0 (April 2026)  
**Status:** ✅ Complete and Ready for Production Deployment
