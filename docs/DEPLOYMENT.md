# MedSync EMR Production Deployment Runbook

**Last Updated:** April 2026  
**Status:** Production-Ready  
**Platform Support:** Vercel (UI), Railway (API), Neon (Database)

> ⚠️ **CRITICAL:** This runbook was updated April 2026 to document WebAuthn/passkey endpoints, AI module infrastructure, push notifications (VAPID), Celery async tasks, and all Phase 2-5 features. Verify all environment variables before deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Database Setup (Neon)](#database-setup-neon)
4. [Backend Deployment (Railway or Vercel)](#backend-deployment-railway-or-vercel)
5. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
6. [Environment Variables](#environment-variables)
7. [SSL/HTTPS Certificate Setup](#ssluihttps-certificate-setup)
8. [Database Migrations](#database-migrations)
9. [Health Check Verification](#health-check-verification)
10. [Rollback Procedure](#rollback-procedure)
11. [Monitoring & Alerting](#monitoring--alerting)
12. [Post-Deployment Validation](#post-deployment-validation)

---

## Prerequisites

### Required Accounts

- **Neon PostgreSQL:** https://neon.tech (Database host)
- **Vercel:** https://vercel.com (Frontend + optionally API)
- **Railway:** https://railway.app (Alternative for API backend)
- **SendGrid/Mailgun/SES:** Email provider for MFA and password reset emails
- **GitHub:** Repository access for CI/CD

### Required Tools (Local Development/Admin Access)

```bash
# Python 3.12+ for backend admin tasks
python --version

# Node.js 18+ for frontend deployment
node --version

# Git for version control
git --version

# psql client (optional, for database debugging)
psql --version

# curl for health checks
curl --version
```

### Git Repository Structure

```
EMR/
├── medsync-backend/        # Django REST API
├── medsync-frontend/       # Next.js frontend
├── docs/                   # Documentation
├── vercel.json             # Root API deployment config
├── asgi.py                 # Django ASGI entry point
├── manage.py               # Django management
├── requirements-vercel.txt # Vercel production dependencies
├── requirements.txt        # All dependencies
└── runtime.txt             # Python version specification
```

---

## Architecture Overview

### Two-Project Deployment Model

MedSync uses **two separate Vercel projects** (or Railway + Vercel) linked to the same GitHub repository:

| Service | Vercel Project | Root Directory | Environment |
|---------|----------------|----------------|------------|
| **API** | `medsync-backend-api` | `.` (repository root) | `production` |
| **UI** | `medsync-frontend-app` | `medsync-frontend/` | `production` |

### Why Two Projects?

- **API project:** Vercel runs `vercel.json` in root, installs Python dependencies, runs Django/ASGI server
- **UI project:** Vercel runs `medsync-frontend/vercel.json`, installs Node.js dependencies, runs Next.js app

**If you set UI root directory to `.` instead of `medsync-frontend/`, the Python install will run and the Next.js app will fail to build.**

### Data Flow

```
User (Browser)
    ↓
[Frontend on Vercel]
    ↓ HTTPS
[API on Railway/Vercel]
    ↓
[PostgreSQL on Neon]

Async Tasks: Celery → Redis (optional)
Email: SendGrid/SMTP
```

---

## Database Setup (Neon)

### Step 1: Create Neon Project

1. Log in to [Neon](https://neon.tech)
2. Create a new project: **Create Project**
3. **SELECT REGION: `aws-af-south-1` (Africa/Cape Town)** ⚠️ CRITICAL
   - **Why Cape Town?** Closest available AWS region to Ghana (5,400km, direct network path)
   - **Latency comparison:**
     - Cape Town: ~40-60ms from Accra
     - Frankfurt: ~100-120ms (5,200km but slower routing)
     - US/Virginia: ~140-180ms (9,000km + transatlantic routing)
   - **Clinical impact:** Response time matters for patient safety systems; Cape Town reduces latency by 40-80ms
4. Name it: `medsync-production`
5. PostgreSQL version: **14+** (recommended 15 or 16)
6. Wait for project initialization (~2 min)

### Step 2: Get Connection String

1. In Neon dashboard, navigate to **Connection String**
2. Copy the full connection string:
   ```
   postgresql://user:password@ep-xxx-xxx.af-south-1.neon.tech/medsync_prod?sslmode=require
   ```
   > **Note:** Region should be `af-south-1` (Africa/Cape Town), not `us-east-1` or `eu-central-1`

3. Set as `DATABASE_URL` environment variable in Railway/Vercel

### Step 3: Create Database User (Optional but Recommended)

For security, create a dedicated database user (not the default):

1. In Neon dashboard, go to **SQL Editor**
2. Run:
   ```sql
   CREATE USER medsync_app WITH PASSWORD 'strong-random-password-here';
   ALTER USER medsync_app CREATEDB;
   GRANT ALL PRIVILEGES ON DATABASE medsync_prod TO medsync_app;
   ```

3. Update connection string to use `medsync_app` user

### Step 4: Verify Connection

```bash
# From your local machine (requires psql installed)
# Use Cape Town region (af-south-1) endpoint
psql "postgresql://medsync_app:password@ep-xxx.af-south-1.neon.tech/medsync_prod?sslmode=require"

# If you get a prompt, connection works!
\dt  # List tables (empty on first run)
\q   # Quit
```

---

## Backend Deployment (Railway or Vercel)

### Option A: Railway (Recommended for Reliability)

Railway is simpler for Django apps and better handles long-running processes.

#### Step 1: Create Railway Project

1. Log in to [Railway](https://railway.app)
2. Create new project
3. Deploy from GitHub
4. Select `kaacquah2/EMR` repository
5. Select branch: `main` (or your deployment branch)

#### Step 2: Configure Django Service

1. In Railway dashboard, add **Python Service**
2. Configure:
   - **Repo Directory:** `.` (root)
   - **Procfile:** `web: gunicorn medsync_backend.wsgi:application --workers=4`
   - **Python Version:** 3.12 (set via `runtime.txt`)

#### Step 3: Configure Environment Variables in Railway

1. In Railway dashboard, go to **Variables**
2. Add all variables from [Environment Variables](#environment-variables) section:

```
DEBUG=False
ENV=production
SECRET_KEY=<generate-with-openssl-rand-hex-32>
DATABASE_URL=postgresql://medsync_app:password@ep-xxx.neon.tech/medsync_prod?sslmode=require
ALLOWED_HOSTS=api.medsync.app,*.railway.app
CORS_ALLOWED_ORIGINS=https://app.medsync.app
SECURE_HTTPS=True
SECURE_HSTS_SECONDS=31536000
CSRF_TRUSTED_ORIGINS=https://app.medsync.app
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<SendGrid API key>
DEFAULT_FROM_EMAIL=MedSync <noreply@medsync.app>
PASSWORD_RESET_FRONTEND_URL=https://app.medsync.app/reset-password
```

#### Step 4: Configure Celery Worker Service — CRITICAL ⚠️

> **CRITICAL:** Celery workers are NOT optional. Without them, the following features silently fail:
> - AI async job processing
> - Invitation expiry notifications
> - TAT (Turnaround Time) breach escalation
> - Medication due reminders
> - Push notifications
> - PDF generation
> - MEWS/NEWS alerts

**Configure Celery Worker:**

1. In Railway dashboard, click **+ New Service**
2. Select **GitHub Repo** → `kaacquah2/EMR`
3. Configure:
   - **Service Name:** `celery-worker`
   - **Start Command:** `celery -A medsync_backend worker --loglevel=info`
   - **Instances:** 1 (or more if high load)
   - **Memory:** 512MB minimum (1GB recommended)

4. Under **Variables**, add all same environment variables as web service:
   - All database/CORS/JWT variables (copy from Step 3)
   - Additional for Celery:
     ```
     CELERY_BROKER_URL=redis://...
     CELERY_RESULT_BACKEND=redis://...
     ```

5. Click **Deploy**

**Celery Worker Logs:**
- Expected output: `[*] celery@<hostname> ready. Waiting for commands.`
- Watch for: `Received task` messages (indicates tasks processing)

#### Step 5: Configure Celery Beat Scheduler — REQUIRED ⚠️

> **REQUIRED:** Celery Beat runs scheduled tasks (appointment no-show marking every 15 minutes, email reminders, etc.)

**Configure Celery Beat:**

1. In Railway dashboard, click **+ New Service**
2. Select **GitHub Repo** → `kaacquah2/EMR`
3. Configure:
   - **Service Name:** `celery-beat`
   - **Start Command:** `celery -A medsync_backend beat --loglevel=info`
   - **Instances:** 1 (MUST be 1; beat scheduler requires singleton)
   - **Memory:** 256MB minimum

4. Under **Variables**, add all same environment variables as web service

5. Click **Deploy**

**Celery Beat Logs:**
- Expected output: `beat: Starting..., Scheduler: `
- Watch for: `Scheduler: Sending due task` (indicates scheduled tasks running)

#### Step 6: Deploy

1. All three services now running:
   - `web` — Django API (gunicorn)
   - `celery-worker` — Async task processing
   - `celery-beat` — Scheduled task scheduler

2. Railway provides three service URLs:
   - Web: `https://your-app.up.railway.app`
   - Celery Worker: Internal only (no URL needed)
   - Celery Beat: Internal only (no URL needed)

#### Step 7: Update DNS (if using custom domain)

1. In Railway, go to **Settings → Custom Domains**
2. Add domain: `api.medsync.app` (points to web service only)
3. Update your DNS provider

---

**CRITICAL DEPLOYMENT CHECKLIST FOR CELERY:**

- [ ] Celery worker service created and deployed
- [ ] Celery beat service created (singleton, 1 instance only)
- [ ] Both services have `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`
- [ ] Redis broker is accessible from services
- [ ] Celery worker logs show "ready. Waiting for commands"
- [ ] Celery beat logs show "Scheduler: Sending due task"
- [ ] No backlog in Celery queue (check Redis)

---

### Option B: Vercel (Alternative)

Vercel also supports Django via `/vercel.json` configuration.

#### Step 1: Create Vercel Project

1. Log in to [Vercel](https://vercel.com)
2. Import Project → GitHub → Select `kaacquah2/EMR`
3. Project name: `medsync-backend-api`
4. **Framework:** None (Django)
5. **Root Directory:** `.` (leave default)
6. Do NOT set `medsync-frontend` root here; that's for the frontend project

#### Step 2: Add Environment Variables in Vercel

1. In Vercel project, go to **Settings → Environment Variables**
2. Add all variables from [Environment Variables](#environment-variables) section
3. Scope: **Production**

#### Step 3: Deploy

1. Click **Deploy**
2. Vercel runs `vercel.json` install + build commands
3. Public URL: `https://medsync-backend-api.vercel.app`

#### Step 4: Use Railway+Vercel for Better Reliability

**Recommended:** Use Railway for API (better Python support) and Vercel for UI (better Next.js support).

---

## Frontend Deployment (Vercel)

### Step 1: Create Vercel Project for Frontend

1. Log in to [Vercel](https://vercel.com)
2. Import Project → GitHub → Select `kaacquah2/EMR`
3. Project name: `medsync-frontend-app`
4. **Framework:** Next.js (auto-detected)
5. **Root Directory:** `medsync-frontend/` (CRITICAL!)
6. **Environment Variables:** See below

### Step 2: Set Environment Variables

In Vercel project settings, add:

```
NEXT_PUBLIC_API_URL=https://api.medsync.app/api/v1
```

This tells the frontend where the API is located.

### Step 3: Configure Build Settings

Vercel auto-configures for Next.js, but verify:

- **Build Command:** `npm run build`
- **Output Directory:** `.next` (auto)
- **Install Command:** `npm ci`

### Step 4: Deploy

1. Click **Deploy**
2. Wait for build (~3-5 min)
3. Public URL: `https://medsync-frontend-app.vercel.app`

### Step 5: Set Custom Domain (Optional)

1. In Vercel project, go to **Settings → Domains**
2. Add: `app.medsync.app`
3. Update DNS provider with Vercel nameservers or CNAME record

---

## Environment Variables

### Critical Production Variables

These **MUST** be set before deploying:

#### Security

```bash
# Generate random 64-character hex string
SECRET_KEY=$(openssl rand -hex 32)
echo $SECRET_KEY

# Set in your deployment platform environment
```

```
# Required in production
DEBUG=False
ENV=production
SECRET_KEY=<64-character-hex-string>
ALLOWED_HOSTS=api.medsync.app,app.medsync.app,.vercel.app,.railway.app

# Require HTTPS and set HSTS
SECURE_HTTPS=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_SSL_REDIRECT=True
```

#### Database

```
# CRITICAL: Use Africa/Cape Town region (af-south-1) for Ghana-based deployment
# Latency improvement: ~40-80ms vs Frankfurt or US/Virginia
DATABASE_URL=postgresql://medsync_app:PASSWORD@ep-xxx.af-south-1.neon.tech/medsync_prod?sslmode=require
```

> **Region Selection for Ghana (CRITICAL FOR LATENCY):**
> - ✅ **CORRECT:** `af-south-1.neon.tech` (Africa/Cape Town) — ~40-60ms from Accra
> - ❌ **INCORRECT:** `eu-central-1.neon.tech` (Frankfurt) — ~100-120ms from Accra
> - ❌ **INCORRECT:** `us-east-1.neon.tech` (US/Virginia) — ~140-180ms from Accra
>
> For clinical systems where response time impacts patient safety, Cape Town latency is critical.

#### CORS & CSRF

```
CORS_ALLOWED_ORIGINS=https://app.medsync.app,https://medsync-frontend-app.vercel.app
CSRF_TRUSTED_ORIGINS=https://app.medsync.app,https://medsync-frontend-app.vercel.app
```

#### JWT & MFA

```
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
WEBAUTHN_RP_ID=app.medsync.app
WEBAUTHN_ORIGIN=https://app.medsync.app
WEBAUTHN_ENABLED=True
```

#### Email (SendGrid Example)

```
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<SendGrid API key>
DEFAULT_FROM_EMAIL=MedSync <noreply@medsync.app>
PASSWORD_RESET_FRONTEND_URL=https://app.medsync.app/reset-password
```

#### Password Recovery

```
PASSWORD_RESET_TOKEN_EXPIRY_HOURS=24
FRONTEND_URL=https://app.medsync.app
```

#### Push Notifications (Web Push / VAPID) — NEW IN 2026

> **REQUIRED FOR:** Push notification infrastructure (appointment reminders, lab results, referral notifications)

Generate VAPID keys using webpush CLI:

```bash
npm install -g web-push
web-push generate-vapid-keys
# Output:
# Public Key: BCxxxxx...
# Private Key: xxxxxx...
```

Set in production:

```
VAPID_PUBLIC_KEY=<public-key-from-web-push>
VAPID_PRIVATE_KEY=<private-key-from-web-push>
VAPID_CLAIM_EMAIL=mailto:admin@medsync.app
```

#### Async Task Queue (Celery) — NEW IN 2026

> **REQUIRED FOR:** Background jobs (no-show marking, AI model training, report generation, appointment reminders)

Requires Redis broker:

```
CELERY_BROKER_URL=redis://:password@redis.railway.app:port/0
CELERY_RESULT_BACKEND=redis://:password@redis.railway.app:port/0
```

Local development (no Redis needed):
```
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

#### AI Module (ML Models & Governance) — NEW IN 2026

> **CRITICAL:** AI infrastructure is production-ready for testing/UX. Models are placeholder (development-stage). See `AI_ML_PRODUCTION_READINESS_CORRECTION.md` for clinical deployment requirements.

```
# AI Feature Toggle (disable if not in use)
AI_GOVERNANCE_ENABLED=True

# Disable AI features temporarily (emergency shutdown)
DISABLE_AI_FEATURES=False

# Confidence threshold for model predictions (0.0-1.0)
# Default 0.5: only predictions with ≥50% confidence are returned
AI_CONFIDENCE_THRESHOLD=0.5

# AI Model Directory (optional: customize location)
# Default: medsync-backend/api/ai/models/
MEDSYNC_AI_MODELS_DIR=/path/to/custom/models
```

#### MFA Configuration

```
# MFA is MANDATORY for all clinical roles (doctor, nurse, lab tech, hospital admin, super admin)
# No [MFA Disabled] path exists in production

# Development only: bypass MFA for local testing
# NEVER set this in production
DEV_BYPASS_MFA=False
```

#### Audit & Security

```
# HMAC signing key for audit log chain signatures
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
AUDIT_LOG_SIGNING_KEY=<random-64-char-key>

# Break-glass emergency access settings
BREAK_GLASS_WINDOW_MINUTES=15
BREAK_GLASS_NOTIFY_EMAILS=admin@hospital.gh,security@hospital.gh
```

#### Optional: Rate Limiting

```
THROTTLE_ANON=60/hour
THROTTLE_USER=1000/hour
```

### Creating `SECRET_KEY` Safely

```bash
# On your local machine (MacOS/Linux)
openssl rand -hex 32

# Output: a1b2c3d4e5f6... (64 characters)

# Copy and paste into your deployment platform's environment variables
```

### Verifying Environment Variables

After deployment, check that critical variables are set:

```bash
# SSH into Railway/Vercel instance (if available)
# Or use curl to indirect check via API response headers

curl -I https://api.medsync.app/api/v1/health
# Should NOT show any debug info in headers if DEBUG=False
```

---

## SSL/HTTPS Certificate Setup

### Vercel (Automatic)

Vercel automatically provisions and renews SSL certificates via Let's Encrypt. No manual setup required.

1. Add custom domain in Vercel project settings
2. Vercel automatically creates certificate (~5 min)
3. Certificate renews automatically before expiration

### Railway (Automatic)

Railway also provides automatic SSL via Let's Encrypt.

1. Add custom domain in Railway settings
2. Certificate provisioned automatically

### Manual HTTPS (If Using Self-Managed Server)

If deploying to a self-managed server, use Certbot:

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate for your domain
sudo certbot certonly --standalone -d api.medsync.app

# Configure Nginx to use certificate
# (See your web server documentation)

# Auto-renewal (runs automatically)
sudo certbot renew --dry-run
```

### Enforce HTTPS in Django

Already configured in `settings.py` when `SECURE_HTTPS=True`:

```python
# settings.py (auto-applied when ENV=production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## Database Migrations

### Before First Deployment

Run migrations locally to test:

```bash
cd medsync-backend

# Activate virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements-vercel.txt

# Create .env with DATABASE_URL pointing to Neon
cp .env.example .env
# Edit .env and add:
# DATABASE_URL=postgresql://user:pass@neon-host/db

# Run migrations
python manage.py migrate
```

### On Deployment Platform

#### Railway

1. In Railway dashboard, navigate to **Deployments**
2. Click on latest deployment
3. In service logs, confirm migration ran automatically:
   ```
   Running Django migrations...
   No migrations to apply.
   ```

If migrations don't run automatically, run manually via Railway shell:

```bash
# SSH into Railway instance
railway shell

# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Exit
exit
```

#### Vercel

Migrations do NOT run automatically on Vercel. Run via Lambda function or manually:

```bash
# Option 1: Use Vercel CLI to run one-off command
vercel env pull .env.production.local
python manage.py migrate --database production

# Option 2: SSH to instance and run
vercel ssh
python manage.py migrate
```

### Migration Checklist

- [ ] Backup production database before migrations
- [ ] Run migrations in staging environment first
- [ ] Monitor migration logs for errors
- [ ] Verify all tables created in production database
- [ ] Test critical API endpoints after migrations

---

## Health Check Verification

### Check API Health

```bash
# Public health endpoint (no authentication required)
curl https://api.medsync.app/api/v1/health

# Expected response (200 OK):
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "email": "configured",
  "timestamp": "2024-12-20T10:00:00Z"
}

# If database unreachable (503):
{
  "status": "unhealthy",
  "database": "unreachable",
  "error": "Database connection refused"
}
```

### Check Frontend Health

```bash
# Frontend base URL
curl https://app.medsync.app

# Expected: HTML response with Next.js app
# (Check for <title>MedSync</title> or similar)
```

### Test Authentication Flow

```bash
# Step 1: Test login endpoint
curl -X POST https://api.medsync.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doctor@medsync.gh","password":"Doctor123!"}'

# Expected response:
{
  "mfa_required": true,
  "mfa_token": "eyJ...",
  "mfa_channel": "email"
}

# Step 2: Verify email was sent for MFA (check inbox)

# Step 3: Test MFA verification
curl -X POST https://api.medsync.app/api/v1/auth/mfa-verify \
  -H "Content-Type: application/json" \
  -d '{"mfa_token":"eyJ...","code":"123456"}'

# Expected: Access token issued
```

### Test Database Connection

```bash
# Connect to Neon with psql
psql "postgresql://medsync_app:password@ep-xxx.neon.tech/medsync_prod?sslmode=require"

# List tables
\dt

# Should show: 
# - core_user
# - patients_patient
# - records_medicalrecord
# - etc.

# Quick query
SELECT COUNT(*) FROM core_user;

# Exit
\q
```

### Monitoring Dashboard

Use Vercel/Railway dashboards for ongoing monitoring:

- **CPU/Memory Usage**
- **Response Times**
- **Error Rates**
- **Database Connection Pool**

---

## Rollback Procedure

### If Deployment Fails Immediately

#### Vercel

1. Go to project **Deployments** tab
2. Click on previous successful deployment
3. Click **⋮ → Promote to Production**
4. Verify rollback in health check

#### Railway

1. Go to **Deployments** tab
2. Select previous successful deployment
3. Click **Redeploy**
4. Confirm redeployment

### If Database Migration Fails

**CRITICAL:** Always backup database before migrations.

```bash
# Backup from Neon
pg_dump "postgresql://user:pass@neon-host/db" > backup.sql

# If migration fails, restore backup
psql "postgresql://user:pass@neon-host/db" < backup.sql

# Then rollback code and re-deploy previous version
```

### Rollback Steps

1. **Identify Issue:** Check logs in Vercel/Railway dashboard
2. **Backup Current Data:** `pg_dump` to local file
3. **Revert Code:** 
   ```bash
   git revert <commit-hash>
   git push origin main
   ```
4. **Re-deploy:** Trigger deployment in Vercel/Railway
5. **Verify Health:** Run health check curl commands
6. **Communicate:** Notify team of rollback

### Prevention

- Always deploy to **staging** environment first
- Run migrations on staging before production
- Use feature flags for major code changes
- Monitor error rates and logs for 1 hour post-deployment

---

## Monitoring & Alerting

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| **CPU Usage** | >80% | Scale up or optimize code |
| **Memory Usage** | >85% | Investigate memory leaks |
| **Database Connections** | >30 (out of 50 max) | Check for connection leaks |
| **API Error Rate** | >1% | Check logs for errors |
| **Response Time (p99)** | >5s | Check slow queries |
| **Auth Failures** | >100/hour | Check for brute-force attacks |

### Enable Monitoring in Vercel

1. In project **Settings → Observability → Enable**
2. Use **Analytics** tab to view:
   - Request volume
   - Error rates
   - Response times
   - Top slow endpoints

### Enable Monitoring in Railway

1. In project **Settings → Monitoring**
2. View:
   - CPU/Memory charts
   - Deployment history
   - Build logs

### Email Alerts

#### Vercel Pro Features

Enable in **Settings → Notifications:**
- Deployment failed
- Error rate spike
- Deployment successful

#### Railway Notifications

Enable in **Project → Notifications:**
- Deployment failure
- Service crash
- High resource usage

### Log Aggregation (Optional)

For enterprise environments, integrate with:
- **Datadog:** `pip install datadog`
- **New Relic:** `pip install newrelic`
- **Sentry:** Error tracking (free tier available)

To add Sentry (Django errors):

```bash
pip install sentry-sdk
```

```python
# settings.py
import sentry_sdk

sentry_sdk.init(
    dsn="https://xxxxx@sentry.io/xxxxx",
    traces_sample_rate=0.1,
    environment="production"
)
```

---

## Post-Deployment Validation

### Comprehensive Health Checks (Run Immediately After Deployment)

#### 1. API Core Health

```bash
# Health check endpoint (no auth required)
curl -s https://api.medsync.app/api/v1/health | jq .
# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "timestamp": "2026-04-19T..."
# }
```

#### 2. Authentication & MFA

```bash
# Test login endpoint
curl -X POST https://api.medsync.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doctor@medsync.gh","password":"Doctor123!"}'

# Expected: MFA token issued (or 403 if MFA not configured)
```

#### 3. WebAuthn/Passkey Endpoints — NEW IN 2026

```bash
# Check if WebAuthn is enabled
curl https://api.medsync.app/api/v1/auth/passkey/registration-options \
  -H "Authorization: Bearer <access_token>" | jq .

# Expected: Valid registration challenge returned
```

#### 4. AI Module Health — NEW IN 2026

```bash
# AI endpoints should respond (even if models are placeholder)
curl https://api.medsync.app/api/v1/ai/health \
  -H "Authorization: Bearer <access_token>" | jq .

# Expected response:
# {
#   "ai_enabled": true,
#   "model_status": "development-stage",
#   "warning": "Placeholder models - not for clinical use"
# }

# Test individual AI endpoints
curl -X POST https://api.medsync.app/api/v1/ai/risk-score \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"test-patient"}' | jq .

# Expected: 200 OK (even if score is placeholder)
```

#### 5. Push Notifications (Web Push) — NEW IN 2026

> **Required:** VAPID keys must be set and valid

```bash
# Check push notification configuration
curl https://api.medsync.app/api/v1/push/vapid-public-key | jq .

# Expected response:
# {
#   "public_key": "BCxxxxx..."
# }

# If empty or 404: VAPID keys not configured
# Set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY in environment
```

#### 6. Celery Async Tasks & Scheduler — CRITICAL NEW IN 2026

> **CRITICAL:** Celery worker and beat scheduler must be running for system to function. Without them, async jobs silently fail.

```bash
# Step 1: Check Redis broker connection
redis-cli -h <redis-host> -p <redis-port> PING
# Expected: PONG

# Step 2: Check Celery worker is processing tasks
# SSH into Railway instance and check logs:
# Should see: "[*] celery@<hostname> ready. Waiting for commands."

# Step 3: Check Celery Beat scheduler is running
# Should see in logs: "beat: Starting..., Scheduler:"

# Step 4: Check scheduled tasks are registered
python manage.py shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.all().count()
# Expected: Should see scheduled tasks like 'mark-no-shows-every-15-minutes'

# Step 5: Verify tasks are actually executing
# Wait 15+ minutes, then check:
>>> from api.models import Appointment
>>> Appointment.objects.filter(status='no_show').count()
# If > 0 after 15 minutes, Celery is processing tasks

# Step 6: Check queue depth (if backed up, reduce workers or increase Redis)
redis-cli LLEN celery
# Expected: < 100 (low backlog)

# Step 7: Manually trigger a test task to verify it processes
python manage.py shell
>>> from api.tasks.appointment_tasks import mark_no_shows_task
>>> result = mark_no_shows_task.apply_async()
>>> result.ready()  # Should become True within 10 seconds
True
```

**CRITICAL SIGNS CELERY IS NOT WORKING:**
- ❌ No "celery@<hostname> ready" message in Celery worker logs
- ❌ No "Scheduler: Sending due task" messages in Beat logs
- ❌ Queue depth growing (redis-cli LLEN celery > 1000)
- ❌ Tasks never complete (result.ready() always False)
- ❌ Appointments not being marked as no-show
- ❌ No push notifications sending
- ❌ AI async jobs not running

**IF CELERY IS NOT WORKING:**
1. Verify Redis is running and accessible
2. Check Celery worker logs for errors
3. Check Celery beat logs for errors
4. Verify CELERY_BROKER_URL and CELERY_RESULT_BACKEND are set correctly
5. Verify both worker and beat services are deployed in Railway
6. Check for Redis connection timeout errors
7. Verify environment variables match between all three services (web, worker, beat)
8. Restart both Celery services


#### 7. Database & Migrations

```bash
# Connect to Neon database
psql postgresql://user:pass@ep-xxx.neon.tech/medsync_prod

# Verify tables exist
\dt

# Expected tables:
# - core_user
# - api_hospital
# - patients_patient
# - records_medicalrecord
# - api_aimodel (new in Phase 8)
# - api_aianalysisresult (new in Phase 8)
# - webpush_subscription (new for push notifications)
# - etc.
```

#### 8. Audit Logging

```bash
# Check audit logs are being created
psql -d medsync_prod -c "SELECT COUNT(*) FROM core_auditlog WHERE created_at > NOW() - INTERVAL '1 hour';"

# Expected: >0 (recent audit entries exist)
```

### Quick Verification Checklist (Run Immediately After Deployment)

- [ ] API health check passes (200 OK)
- [ ] Frontend loads in browser (no 404 errors)
- [ ] Login page accessible
- [ ] Login with test account works
- [ ] MFA code received and verified
- [ ] WebAuthn registration/authentication endpoints respond
- [ ] **AI endpoints respond (even if placeholder models)** — ✨ NEW
- [ ] **Push notification VAPID key available** — ✨ NEW
- [ ] **Celery worker running and processing tasks** — ✨ NEW
- [ ] Patient search works
- [ ] Can view patient records
- [ ] Database tables exist (`\dt` in psql)
- [ ] Audit logs created for test actions
- [ ] No 500 errors in logs
- [ ] SSL certificate valid (check browser padlock)

### Checklist (Run Within 24 Hours)

- [ ] Email sends working (check password reset)
- [ ] **Push notifications sending (test appointment reminder)** — ✨ NEW
- [ ] **AI model predictions generating (even if placeholder)** — ✨ NEW
- [ ] **Celery scheduled tasks executing** (verify no-show marking runs) — ✨ NEW
- [ ] **Redis/Celery broker connection stable** — ✨ NEW
- [ ] File uploads working
- [ ] Database backups scheduled
- [ ] Monitoring dashboards showing data
- [ ] No unusual error patterns

### Checklist (Run Weekly)

- [ ] All API endpoints returning expected responses
- [ ] **All AI endpoints responding with reasonable latency (<5s)** — ✨ NEW
- [ ] **Push subscription management working** (subscribe/unsubscribe endpoints) — ✨ NEW
- [ ] **Celery task queue not backing up** (check Redis key count) — ✨ NEW
- [ ] Cross-facility referrals working
- [ ] Consent workflows functioning
- [ ] Break-glass access fully audited
- [ ] Audit logs exportable
- [ ] Reports generating without timeout
- [ ] Database backups confirmed

---

## Troubleshooting Deployment Issues

### 502 Bad Gateway

**Cause:** Backend not responding

**Solution:**
1. Check backend logs: `railway logs` or Vercel dashboard
2. Verify database connection: `curl https://api.medsync.app/api/v1/health`
3. Check environment variables (SECRET_KEY, DATABASE_URL)
4. Redeploy

### 404 Not Found on Frontend

**Cause:** Wrong root directory in Vercel

**Solution:**
1. In Vercel UI project settings: **Root Directory** → `medsync-frontend/`
2. Redeploy

### Database Connection Refused

**Cause:** Neon firewall or wrong DATABASE_URL

**Solution:**
1. Verify DATABASE_URL: `echo $DATABASE_URL`
2. Test connection locally: `psql $DATABASE_URL`
3. Check Neon firewall: https://console.neon.tech → **Project Settings → IP Whitelist**
4. Add Railway/Vercel IP addresses to whitelist (Neon handles this automatically for Vercel)

### Email Not Sending

**Cause:** SMTP credentials wrong or email service misconfigured

**Solution:**
1. Verify SendGrid API key: `curl -X GET https://api.sendgrid.com/v3/user/account -H "Authorization: Bearer $SENDGRID_API_KEY"`
2. Check EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
3. Check DEFAULT_FROM_EMAIL format
4. Test: `python manage.py shell` → `send_mail(...)`

### Migration Fails

**Cause:** Data conflict or circular dependency

**Solution:**
1. Check migration logs
2. Backup database
3. Manually fix conflicting data
4. Retry migration

### AI Endpoints Return 500 or "Model Not Found" — NEW IN 2026

**Cause:** AI models not loaded or VAPID keys missing

**Solution:**
1. Verify `DISABLE_AI_FEATURES=False` (if True, AI endpoints disabled)
2. Check AI model files exist: `ls medsync-backend/api/ai/models/`
3. Verify `MEDSYNC_AI_MODELS_DIR` points to correct path
4. Check logs: `grep "Error loading model" <logs>` or Railway logs
5. AI is in development-stage; placeholder models are normal. For clinical deployment, see `AI_ML_PRODUCTION_READINESS_CORRECTION.md`

### Push Notifications Not Sending — NEW IN 2026

**Cause:** VAPID keys missing or Redis not connected

**Solution:**
1. Verify VAPID keys set:
   ```bash
   curl https://api.medsync.app/api/v1/push/vapid-public-key
   # Should NOT be empty
   ```
2. Check Redis connection: `redis-cli PING` → should return PONG
3. Verify `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` match (generated as a pair)
4. Test subscription: Create test subscription and verify it's stored in database
5. Check `webpush_subscription` table has records

### Celery Tasks Not Executing — CRITICAL NEW IN 2026

**This is a CRITICAL issue.** Without Celery workers, the following features silently fail:
- AI async job processing
- Invitation expiry notifications
- TAT breach escalation
- Medication due reminders
- Push notifications
- PDF generation
- MEWS alerts

**Cause:** Redis not running, Celery worker service not deployed, or queue backed up

**Solution:**

1. **Verify Celery worker is deployed in Railway:**
   ```bash
   # In Railway dashboard, check for THREE services:
   - web (Django API with gunicorn)
   - celery-worker (Celery worker service)
   - celery-beat (Celery beat scheduler)
   # If any are missing, add them (see Railway setup section)
   ```

2. **Check Celery worker logs:**
   ```bash
   # In Railway dashboard, click celery-worker service → Logs
   # Should see: "[*] celery@<hostname> ready. Waiting for commands."
   # If not, check for errors like "Connection refused" (Redis not accessible)
   ```

3. **Check Celery beat logs:**
   ```bash
   # In Railway dashboard, click celery-beat service → Logs
   # Should see: "beat: Starting..., Scheduler:"
   # Should see: "Scheduler: Sending due task" messages every 15 minutes
   ```

4. **Verify Redis connection:**
   ```bash
   redis-cli -h <redis-host> -p <redis-port> PING
   # Expected: PONG
   # If timeout: Redis not accessible from Railway
   ```

5. **Check queue depth:**
   ```bash
   redis-cli LLEN celery
   # Expected: < 100 (low backlog)
   # If > 1000: Queue backed up, increase workers or optimize tasks
   ```

6. **Verify environment variables on both services:**
   ```
   # Celery worker AND Celery beat must have:
   CELERY_BROKER_URL=redis://...
   CELERY_RESULT_BACKEND=redis://...
   DATABASE_URL=... (same as web service)
   # If different, tasks may fail to connect to broker
   ```

7. **Check task execution manually:**
   ```python
   python manage.py shell
   >>> from api.tasks.appointment_tasks import mark_no_shows_task
   >>> result = mark_no_shows_task.apply_async()
   >>> result.ready()  # Should become True within 10 seconds
   True
   ```

8. **Restart Celery if needed:**
   ```bash
   # In Railway:
   # - Click celery-worker service → Settings → Restart
   # - Click celery-beat service → Settings → Restart
   # - Monitor logs for "ready" message
   ```

9. **Check for specific task failures:**
   ```python
   python manage.py shell
   >>> from celery.result import AsyncResult
   >>> result = AsyncResult('<task-id>')
   >>> result.status  # Can be PENDING, STARTED, SUCCESS, FAILURE
   >>> result.result  # Error message if FAILURE
   ```

**Common Error Messages and Fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` in Celery logs | Redis not accessible | Verify CELERY_BROKER_URL, check Redis credentials |
| `kombu.exceptions.OperationalError` | Broker connection failed | Verify Redis is running, check firewall rules |
| `[*] celery@... ready` but no tasks | Beat scheduler not running | Verify celery-beat service is deployed |
| Queue depth > 1000 | Too many tasks, workers too slow | Increase worker instances or optimize task code |
| Tasks never complete | Worker crashed or hung | Check worker logs, restart service |

---

### WebAuthn/Passkey Endpoints 404 — NEW IN 2026

**Cause:** `WEBAUTHN_ENABLED=False` or migration not run

**Solution:**
1. Verify `WEBAUTHN_ENABLED=True`
2. Verify `UserPasskey` model table exists: `psql $DATABASE_URL -c "\dt *passkey"`
3. Run migrations: `python manage.py migrate`
4. Restart backend

---

## Maintenance Tasks

### Daily

- Monitor API error rates in dashboards
- Check audit logs for security anomalies
- Verify database connection health
- **Check Celery task queue depth (Redis)** — ✨ NEW
- **Monitor AI endpoint response times** — ✨ NEW

### Weekly

- Review database size (pg_stat_statements in Neon)
- Audit file upload directory usage
- Check scheduled task execution
- **Verify Celery beat scheduler running (no-show marking every 15 min)** — ✨ NEW
- **Confirm push notification queue emptying** — ✨ NEW
- **Check AI model inference latency (<5s avg)** — ✨ NEW

### Monthly

- Review and update dependencies: `pip audit`, `npm audit`
- Backup user data for compliance
- Analyze database query performance
- Review cost/usage metrics
- **Analyze AI endpoint usage (which models used most, error rates)** — ✨ NEW
- **Review Celery task execution times and failures** — ✨ NEW
- **Confirm WebAuthn/passkey adoption among users** — ✨ NEW

### Quarterly

- Update SSL certificates (if not auto-renewed)
- Test disaster recovery procedures
- Security audit of deployed code
- Load testing (simulated 1000+ concurrent users)
- **AI model retraining evaluation (if clinical deployment planned)** — ✨ NEW
- **Celery infrastructure scale testing** — ✨ NEW

---

## Security Checklist (Pre-Production) — UPDATED APRIL 2026

- [ ] `DEBUG=False` in production
- [ ] `SECRET_KEY` is cryptographically random (64+ chars)
- [ ] HTTPS enforced (SECURE_HTTPS=True)
- [ ] HSTS enabled (SECURE_HSTS_SECONDS=31536000)
- [ ] CORS restricted to known domains (not `*`)
- [ ] Database password strong and unique
- [ ] Neon firewall whitelist configured
- [ ] Email credentials securely stored (not in git)
- [ ] **VAPID keys generated and stored securely (not in git)** — ✨ NEW
- [ ] **DEV_BYPASS_MFA=False in production (MFA mandatory)** — ✨ NEW
- [ ] **AI_CONFIDENCE_THRESHOLD set appropriately (0.5 recommended)** — ✨ NEW
- [ ] **Celery Redis broker password strong and connection encrypted** — ✨ NEW
- [ ] **Backup strategy documented and tested**
- [ ] Logging configured for audit trail
- [ ] Rate limiting enabled
- [ ] RBAC enforced at API layer
- [ ] Penetration testing completed
- [ ] **AI models identified as development-stage (not clinical-ready)** — ✨ NEW

---

## Support & Resources

- **Railway Docs:** https://docs.railway.app/deploy/deployments
- **Vercel Docs:** https://vercel.com/docs
- **Neon Docs:** https://neon.tech/docs/introduction
- **Django Deployment:** https://docs.djangoproject.com/en/4.2/howto/deployment/
- **GitHub Issues:** https://github.com/kaacquah2/EMR/issues

---

## Next Steps After Deployment — UPDATED APRIL 2026

1. **Run Full Post-Deployment Validation** (see [Post-Deployment Validation](#post-deployment-validation))
   - Verify health checks for core features, WebAuthn, AI, push notifications, and Celery
   
2. **Verify New Features Working:**
   - ✅ WebAuthn/passkey registration and authentication
   - ✅ AI module endpoints responding (models are placeholder; clinical deployment roadmap in `AI_ML_PRODUCTION_READINESS_CORRECTION.md`)
   - ✅ Push notifications VAPID keys configured
   - ✅ Celery tasks executing (especially no-show marking every 15 minutes)

3. **Configure AI for Your Environment** (CRITICAL):
   - Read: `AI_ML_PRODUCTION_READINESS_CORRECTION.md`
   - Current status: **Infrastructure production-ready, models development-stage**
   - Clinical use requires: 9+ months data collection, model training, validation, regulatory review
   - Do NOT deploy placeholder models to clinical workflows without this work

4. **Announce Deployment:** Notify hospital administrators
   - Include note about AI infrastructure being ready for testing/UX only
   - Provide WebAuthn/passkey setup instructions for clinicians
   - Document push notification subscription process
   
5. **Train Users:** Conduct system training for new staff
   - WebAuthn/passkey setup
   - New push notification features
   - AI module limitation (development-stage, for testing)

6. **Monitor Continuously:** Watch dashboards for 48 hours
   - Check AI endpoint response times
   - Monitor Celery task queue
   - Verify push notification delivery rate
   - Watch for Redis connection issues

7. **Document Lessons Learned:** Record any issues encountered

8. **Plan for AI Clinical Deployment** (when ready):
   - Follow 4-phase roadmap in `AI_ML_CLINICAL_DEPLOYMENT_ROADMAP.md`
   - Budget 9+ months for data collection, model training, validation
   - Plan regulatory/compliance review before clinical use

### Resources & Documentation

- **Deployment Guide:** This file (DEPLOYMENT.md)
- **AI Production Readiness:** `docs/AI_ML_PRODUCTION_READINESS_CORRECTION.md`
- **AI Clinical Deployment Roadmap:** `docs/AI_ML_CLINICAL_DEPLOYMENT_ROADMAP.md`
- **MFA Requirements:** `docs/MFA_MANDATORY_REQUIREMENT_CORRECTION.md`
- **JWT Security:** `docs/JWT_ALGORITHM_SECURITY_FIX.md`
- **WebAuthn/Passkey:** `docs/ARCHITECTURE.md` (Section: Authentication Layer)
- **Celery Configuration:** `medsync-backend/medsync_backend/settings.py` (lines 617-653)
- **Push Notifications:** `medsync-backend/medsync_backend/settings.py` (lines 488-491)

### Support

- **Railway Docs:** https://docs.railway.app/deploy/deployments
- **Vercel Docs:** https://vercel.com/docs
- **Neon Docs:** https://neon.tech/docs/introduction
- **Django Deployment:** https://docs.djangoproject.com/en/4.2/howto/deployment/
- **GitHub Issues:** https://github.com/kaacquah2/EMR/issues

For additional deployment support, contact the infrastructure team or file an issue on GitHub.

---

**Deployment Runbook Last Updated:** April 19, 2026  
**Status:** ✅ Current, covers all major features through Phase 8.2  
**Next Review:** After next major feature release
