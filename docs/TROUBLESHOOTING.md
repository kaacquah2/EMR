# MedSync EMR Production Troubleshooting Guide

**Version:** 1.0  
**Last Updated:** December 2024  
**Audience:** System Administrators, DevOps Engineers, Hospital IT Staff

---

## Table of Contents

1. [Database Connection Refused](#issue-1-database-connection-refused)
2. [JWT Token Expired/Refresh Failing](#issue-2-jwt-token-expiredrefresh-failing)
3. [TOTP Code Not Accepted](#issue-3-totp-code-not-accepted)
4. [WebAuthn Registration Fails](#issue-4-webauthn-registration-fails)
5. [CORS Errors in Browser Console](#issue-5-cors-errors-in-browser-console)
6. [File Upload Size Limit Exceeded](#issue-6-file-upload-size-limit-exceeded)
7. [Email Not Sending](#issue-7-email-not-sending)
8. [Superuser Account Locked](#issue-8-superuser-account-locked)

---

## Issue 1: Database Connection Refused

### Symptoms

- API logs show: `psycopg2.OperationalError: could not connect to server`
- API health check (`GET /health`) returns 503 with database: "unreachable"
- Requests to API endpoints fail with 500 errors
- Production database migration failed during deployment

### Root Causes

| Cause | Likelihood | Severity |
|-------|------------|----------|
| Neon connection string invalid | High | Critical |
| Neon database not running | Medium | Critical |
| Firewall blocking connection | Medium | Critical |
| Password expired | Low | Critical |
| Network connectivity issue | Low | Critical |

### Diagnosis Steps

#### Step 1: Verify Connection String

```bash
# Check DATABASE_URL is set in your deployment platform
# Railway: Settings → Variables → look for DATABASE_URL
# Vercel: Settings → Environment Variables → look for DATABASE_URL

# Expected format:
# postgresql://user:password@ep-xxx.region.neon.tech/dbname?sslmode=require

# Verify it's not empty
echo $DATABASE_URL

# If empty, connection will fail immediately
```

#### Step 2: Test Connection Locally

```bash
# On your local machine with psql installed
psql "postgresql://user:password@ep-xxx.region.neon.tech/dbname?sslmode=require"

# If successful: psql prompt appears
# If failed: "Error: could not translate host name..."
```

#### Step 3: Check Connection URL Format

Common mistakes in DATABASE_URL:

| Mistake | Correct |
|---------|---------|
| `postgresql://user@password:host` | `postgresql://user:password@host` |
| `postgres://` (old format) | `postgresql://` (new format) |
| Missing `?sslmode=require` | Include `?sslmode=require` |
| Port in URL without colon | `host:5432` (not `host5432`) |

```bash
# Verify URL structure
# postgresql://USERNAME:PASSWORD@HOSTNAME:PORT/DBNAME?sslmode=require

# Example valid URL:
# postgresql://medsync_app:SecurePass123@ep-cool-base-123456.us-east-1.neon.tech/medsync_prod?sslmode=require
```

#### Step 4: Check Neon Firewall Rules

1. Log in to [Neon Console](https://console.neon.tech)
2. Select project: `medsync-production`
3. Navigate to **Project Settings → IP Whitelist**
4. Verify your deployment IP is whitelisted:
   - For Vercel: Vercel auto-whitelists (should appear automatically)
   - For Railway: Railway IP should be added automatically
   - For local testing: Add your machine's public IP

To get your IP:

```bash
# On your local machine
curl https://ifconfig.me

# Output: your public IP (e.g., 203.0.113.42)
```

#### Step 5: Check Neon Project Status

1. In Neon console, verify database is running
2. Check **Project Health** dashboard
3. Verify no active incidents or maintenance

### Solution

**Option A: Fix Connection String (Most Common)**

```bash
# 1. Get correct connection string from Neon
# Navigate to: https://console.neon.tech → Select Project → Connection String

# 2. Copy the full connection string (it includes password)

# 3. Update in your deployment platform:
#    - Railway: Settings → Variables → edit DATABASE_URL
#    - Vercel: Settings → Environment Variables → edit DATABASE_URL

# 4. Redeploy the application
```

**Option B: Restart Database**

```bash
# If connection string is correct but connection still fails:
# 1. In Neon console, go to Project Settings → Compute
# 2. Click "Restart Compute"
# 3. Wait 2-3 minutes for restart to complete
# 4. Test connection again
```

**Option C: Add IP to Whitelist**

```bash
# If connection string is correct but "host not recognized":
# 1. In Neon console, go to Project Settings → IP Whitelist
# 2. Add Railway/Vercel IP or your office public IP
# 3. Save changes
# 4. Retry connection (may take 30 seconds to propagate)
```

### Prevention

- ✅ Store DATABASE_URL in secure environment (never in git)
- ✅ Test connection before deploying
- ✅ Use strong, randomly generated passwords
- ✅ Enable Neon firewall for security
- ✅ Monitor connection pool usage

---

## Issue 2: JWT Token Expired/Refresh Failing

### Symptoms

- Frontend logs show: `401 Unauthorized: Token is expired`
- "Please log in again" message appears
- Refresh token request fails with 401
- Users kicked out after 15 minutes of activity
- After logout, re-login fails (refresh token blacklisted error)

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| Access token TTL too short | Medium | UX impact (must re-login frequently) |
| Refresh token blacklisted | Medium | Users must re-login completely |
| Clock skew between servers | Low | Intermittent auth failures |
| Token blacklist DB full | Low | Some old tokens won't blacklist |
| Client storing tokens in localStorage | Medium | Tokens persist on shared devices |

### Diagnosis Steps

#### Step 1: Check Token TTL Configuration

```bash
# Expected values (production safe defaults):
# JWT_ACCESS_MINUTES=15        # Access token valid for 15 min
# JWT_REFRESH_DAYS=7           # Refresh token valid for 7 days

# Check current settings in deployment platform
# Railway: Settings → Variables → look for JWT_ACCESS_MINUTES
# Vercel: Settings → Environment Variables → look for JWT_ACCESS_MINUTES

# If not set, Django uses defaults (usually 5 min)
# This causes users to re-login very frequently
```

#### Step 2: Verify Token Format

```bash
# In browser console, check stored token:
console.log(localStorage.getItem('access_token'))  // or sessionStorage

# Valid JWT format: three sections separated by dots
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzIn0.TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ

# Decode token (do NOT send to untrusted websites):
# Use jwt.io or decode locally:
import jwt
decoded = jwt.decode(token, options={"verify_signature": False})
print(decoded['exp'])  # Expiration timestamp
```

#### Step 3: Check Server Clock

```bash
# If tokens work sporadically, check server clock skew
# On deployment server:
date

# Compare to your local machine:
date

# If difference > 5 minutes, this is the problem
# Most cloud providers auto-sync; check if NTP is enabled
```

#### Step 4: Test Refresh Endpoint

```bash
# Get a valid refresh token from login:
curl -X POST https://api.medsync.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doctor@medsync.gh","password":"Doctor123!"}'

# Response includes refresh_token:
{
  "refresh_token": "eyJ..."
}

# Now test refresh:
curl -X POST https://api.medsync.app/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh":"eyJ..."}'

# Should return new access token (200 OK)
# If 401, the token is blacklisted

# Check if token was blacklisted:
SELECT * FROM token_blacklist_blacklistedtoken WHERE token LIKE '%...'
```

#### Step 5: Check Logout History

```bash
# If refresh fails after logout, token should be blacklisted
# Verify in database:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM token_blacklist_blacklistedtoken;"

# If count is very high (>100k), consider archiving old entries:
psql $DATABASE_URL -c "DELETE FROM token_blacklist_blacklistedtoken WHERE blacklisted_at < NOW() - INTERVAL '30 days';"
```

### Solution

**Option A: Set Appropriate JWT Timings (Most Common)**

```bash
# In your deployment platform, set:
JWT_ACCESS_MINUTES=15      # 15 minutes (reasonable for clinical use)
JWT_REFRESH_DAYS=7         # 7 days (prevent frequent re-login)

# After setting, redeploy the application
# Existing tokens expire at old TTL; new tokens use new TTL
```

**Option B: Clear Blacklist (If Refresh Fails After Logout)**

```bash
# If refresh token is incorrectly blacklisted:
psql $DATABASE_URL

# Find and delete the erroneous blacklist entry:
DELETE FROM token_blacklist_blacklistedtoken 
WHERE blacklisted_at < NOW() - INTERVAL '7 days';

# Or completely clear all old entries:
DELETE FROM token_blacklist_blacklistedtoken 
WHERE blacklisted_at < NOW() - INTERVAL '30 days';

\q
```

**Option C: Fix Client-Side Token Storage**

```javascript
// ❌ WRONG: Store in localStorage (persists on shared devices)
localStorage.setItem('access_token', token)

// ✅ CORRECT: Store in sessionStorage (lost on browser close)
sessionStorage.setItem('access_token', token)

// Or store in memory only (most secure):
let accessToken = token;  // Lost on page refresh
```

**Option D: Resync Server Clocks**

```bash
# If clock skew detected, enable NTP:
# On Ubuntu:
sudo apt-get install ntp
sudo systemctl enable ntp
sudo systemctl start ntp

# Verify sync:
timedatectl status
```

### Prevention

- ✅ Set JWT_ACCESS_MINUTES and JWT_REFRESH_DAYS appropriately
- ✅ Use sessionStorage for tokens, never localStorage
- ✅ Implement automatic token refresh (on 401 response)
- ✅ Monitor clock skew on servers
- ✅ Archive old blacklist entries monthly

---

## Issue 3: TOTP Code Not Accepted

### Symptoms

- "Invalid code. Try again." error when entering TOTP
- Backup codes work but TOTP doesn't
- TOTP code was correct but changed (time-based)
- MFA locked after 3 failed attempts
- User can't set up authenticator app

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| Device clock not synchronized | High | TOTP always fails (or on specific devices) |
| User scanning wrong QR code | High | Code will always be wrong |
| Wrong TOTP secret stored | Medium | Code never matches |
| MFA rate limit exceeded | Medium | Account temporarily locked |
| Authenticator app corrupted | Low | Must re-add to new device |

### Diagnosis Steps

#### Step 1: Check Device Time

TOTP codes are time-based and expire every 30 seconds. Device clock must be accurate.

```bash
# On user's device:
date

# Should match current time within 1 minute
# If off by more than 1 minute, TOTP codes won't match

# To fix:
# - iPhone/iPad: Settings → General → Date & Time → toggle "Set Automatically"
# - Android: Settings → System → Date & Time → toggle "Automatic"
# - Windows: Settings → Time & Language → Date & Time → Sync Now
# - macOS: System Preferences → Date & Time → toggle "Set date and time automatically"
```

#### Step 2: Verify TOTP Secret was Saved

During MFA setup, a QR code is scanned. Verify the secret was saved:

```bash
# In database, check user's TOTP secret:
psql $DATABASE_URL -c "SELECT id, email, account_status FROM core_user WHERE email='doctor@medsync.gh';"

# Get user UUID and check:
SELECT * FROM otp_totp_device WHERE user_id='<uuid>' AND confirmed=true;

# Should show one row with confirmed=true
# If no row, TOTP was never activated
# If confirmed=false, user needs to re-scan QR code
```

#### Step 3: Test TOTP Code Generation

```bash
# Manually verify TOTP code is correct:
python3 -c "
import pyotp
import time

# Replace with actual secret from database
secret = 'JBSWY3DPEBLW64TMMQ======'
totp = pyotp.TOTP(secret)

# Get current code
print('Current code:', totp.now())

# Code should match what user sees in authenticator app
# Both should change in 30 seconds
"
```

#### Step 4: Check MFA Rate Limits

```bash
# If user is locked out after 3-5 failed attempts:
psql $DATABASE_URL

# Check failed attempts:
SELECT COUNT(*) FROM core_auditlog 
WHERE user_id='<user-uuid>' 
  AND action='MFA_FAILED' 
  AND timestamp > NOW() - INTERVAL '1 hour';

# Hard limit: 10 failures in 1 hour locks account
# Check if account is locked:
SELECT locked_until FROM core_user WHERE id='<user-uuid>';

# If locked_until is in future, account is locked temporarily
```

#### Step 5: Verify Authenticator App

```bash
# Ask user to:
# 1. Open authenticator app (Google Authenticator, Authy, Microsoft Authenticator)
# 2. Find "MedSync" or "<hospital-name>" entry
# 3. Note current 6-digit code
# 4. Wait 30 seconds and verify code changed
# 5. If code doesn't match server generation, app is corrupted
```

### Solution

**Option A: Sync User Device Clock (Most Common)**

```
1. Ask user to verify device time in settings
2. Ensure "Automatic" or "Automatic Date & Time" is enabled
3. If still wrong, restart device
4. Re-open authenticator app and note current code
5. Retry TOTP login
```

**Option B: Remove and Re-Add Authenticator App**

```
1. In MedSync UI, navigate to Settings → Security → MFA
2. Click "Remove Authenticator" (requires current password)
3. Click "Set Up MFA" again
4. Scan NEW QR code with authenticator app (from Google Authenticator, Authy, etc.)
5. Enter 6-digit code to verify
6. Save backup codes in safe location
```

**Option C: Unlock Account After Rate Limit**

```bash
# If account locked after too many failures:
psql $DATABASE_URL

# Check lock status:
SELECT locked_until FROM core_user WHERE email='doctor@medsync.gh';

# If locked_until > NOW(), account is locked
# Solution: Wait 1 hour OR manually unlock:
UPDATE core_user SET locked_until=NULL WHERE email='doctor@medsync.gh';

# Or use hospital admin reset MFA endpoint:
# POST /admin/users/<user-id>/reset-mfa (requires hospital admin auth)
```

**Option D: Use Backup Code**

```
1. If user has backup codes from MFA setup:
   - Enter one backup code instead of TOTP code
   - Login will succeed
   - Backup code is consumed (single-use)
2. User should immediately fix authenticator or set up new method
```

### Prevention

- ✅ Provide clear instructions for device time sync
- ✅ Save backup codes in secure location during setup
- ✅ Test TOTP code immediately after setup
- ✅ Support multiple authenticator apps (Google, Authy, Microsoft)
- ✅ Hospital admin can reset MFA for locked accounts

---

## Issue 4: WebAuthn Registration Fails

### Symptoms

- "RP ID mismatch" or "Origin mismatch" error during passkey setup
- "NotAllowedError: Operation not allowed" during registration
- Passkey registration silently fails (button disabled after click)
- Cross-browser passkey doesn't work (e.g., created on Android, used on desktop)

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| WEBAUTHN_RP_ID mismatch | High | Registration fails with security error |
| WEBAUTHN_ORIGIN mismatch | High | Registration fails with origin error |
| Browser doesn't support WebAuthn | Medium | Feature unavailable (expected) |
| Passkey not synced across devices | Medium | Can't use passkey on different device |

### Diagnosis Steps

#### Step 1: Verify WebAuthn Configuration

```bash
# Check deployment environment:
# WEBAUTHN_RP_ID should match your domain (without https://)
# WEBAUTHN_ORIGIN should match frontend URL (with https://)

# Example correct configuration:
# WEBAUTHN_RP_ID=app.medsync.app
# WEBAUTHN_ORIGIN=https://app.medsync.app
# WEBAUTHN_ENABLED=True

# Check in deployment platform:
# Railway: Settings → Variables → look for WEBAUTHN_*
# Vercel: Settings → Environment Variables → look for WEBAUTHN_*

# Verify values:
# - RP_ID should NOT include https:// or /path
# - ORIGIN should include https:// and no trailing /
```

#### Step 2: Check Frontend vs Backend Domain Mismatch

```
Common mistakes:

❌ WEBAUTHN_RP_ID=https://app.medsync.app  (includes https://)
✅ WEBAUTHN_RP_ID=app.medsync.app

❌ WEBAUTHN_ORIGIN=app.medsync.app  (no https://)
✅ WEBAUTHN_ORIGIN=https://app.medsync.app

❌ WEBAUTHN_RP_ID=app.medsync.app:8000  (includes port in production)
✅ WEBAUTHN_RP_ID=app.medsync.app  (no port for standard HTTPS)

❌ Frontend URL is https://app.medsync.app but WEBAUTHN_RP_ID=localhost
✅ Both must match production domain
```

#### Step 3: Test WebAuthn Endpoint Directly

```bash
# Get WebAuthn registration challenge from API:
curl -X POST https://api.medsync.app/api/v1/auth/passkey/register/begin \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'

# Response should include:
{
  "challenge": "<base64-encoded-challenge>",
  "rp": {
    "name": "MedSync",
    "id": "app.medsync.app"  # ← Must match WEBAUTHN_RP_ID
  },
  "user": { ... }
}

# If RP ID in response doesn't match WEBAUTHN_RP_ID, update config
```

#### Step 4: Check Browser Support

```javascript
// In browser console, check WebAuthn support:
if (window.PublicKeyCredential) {
  console.log("✓ WebAuthn supported");
  PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
    .then(available => {
      if (available) {
        console.log("✓ Platform authenticator available (fingerprint/face)");
      } else {
        console.log("✗ Platform authenticator NOT available");
      }
    });
} else {
  console.log("✗ WebAuthn NOT supported");
}

// Supported browsers: Chrome 67+, Firefox 60+, Safari 13+, Edge 18+
// Not supported: IE, older mobile browsers
```

#### Step 5: Check for TLS Certificate Issues

```bash
# WebAuthn requires secure context (HTTPS)
# Check certificate:
openssl s_client -connect app.medsync.app:443 -servername app.medsync.app

# Should show valid certificate with your domain
# If certificate doesn't match domain, WebAuthn fails
```

### Solution

**Option A: Fix Configuration (Most Common)**

```bash
# 1. Get your correct production domain:
#    Example: app.medsync.app

# 2. Update in deployment platform:
WEBAUTHN_RP_ID=app.medsync.app       # No https://, no path
WEBAUTHN_ORIGIN=https://app.medsync.app  # With https://, no trailing /
WEBAUTHN_ENABLED=True

# 3. Redeploy application

# 4. Clear browser cache (Ctrl+Shift+Delete) and retry
```

**Option B: Test with localhost (Development Only)**

```bash
# For local testing:
WEBAUTHN_RP_ID=localhost
WEBAUTHN_ORIGIN=http://localhost:3000
WEBAUTHN_ENABLED=True

# Note: localhost WebAuthn only works on http://localhost:3000 (not https)
```

**Option C: Use Sync Passkey (Cross-Device)**

```
For iOS/Android passkeys to work on desktop:

1. Create passkey on iOS using Face ID/Touch ID
2. Passkey automatically syncs to iCloud
3. On desktop browser, use iCloud+ to access passkey
   - Check: Settings → Passwords → iCloud Keychain sync enabled
   
For Android:
1. Create passkey with biometric
2. Enable Google Password Manager sync
3. On desktop, sign in with same Google account
```

### Prevention

- ✅ Verify WEBAUTHN_RP_ID and WEBAUTHN_ORIGIN in production config
- ✅ Test passkey registration immediately after deployment
- ✅ Document supported browsers and devices
- ✅ Provide fallback MFA (TOTP) in case WebAuthn unavailable
- ✅ Use sync passkeys for best cross-device experience

---

## Issue 5: CORS Errors in Browser Console

### Symptoms

- Browser console shows: `Access to XMLHttpRequest... has been blocked by CORS policy`
- Frontend cannot reach backend API
- Login page loads but authentication fails silently
- API works with curl/Postman but not in browser

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| CORS_ALLOWED_ORIGINS misconfigured | High | All frontend requests blocked |
| Frontend URL not in allowlist | High | Frontend cannot access API |
| Credentials not sent with requests | Medium | Authentication endpoints fail |
| Preflight request fails | Medium | POST/PATCH requests blocked |

### Diagnosis Steps

#### Step 1: Check CORS Configuration

```bash
# Check deployment environment:
CORS_ALLOWED_ORIGINS=https://app.medsync.app,https://medsync-frontend-app.vercel.app

# Should include:
# - Frontend domain (with https://, no trailing /)
# - Backup frontend domains (if using multiple)
# - NOT * (avoid wildcard in production)

# Example configuration:
CORS_ALLOWED_ORIGINS=https://app.medsync.app,https://staging-app.medsync.app

# Verify in deployment platform:
# Railway: Settings → Variables → CORS_ALLOWED_ORIGINS
# Vercel: Settings → Environment Variables → CORS_ALLOWED_ORIGINS
```

#### Step 2: Check Browser Console for Exact Error

```javascript
// In browser DevTools Console, look for error like:
// "Access to XMLHttpRequest at 'https://api.medsync.app/api/v1/auth/login'
//  from origin 'https://app.medsync.app' has been blocked by CORS policy:
//  No 'Access-Control-Allow-Origin' header is present on the requested resource."

// This tells you:
// - Requested URL: https://api.medsync.app/api/v1/auth/login
// - Origin: https://app.medsync.app
// - Problem: CORS header missing

// The origin (https://app.medsync.app) is probably not in CORS_ALLOWED_ORIGINS
```

#### Step 3: Test CORS with curl (to verify backend is responding correctly)

```bash
# Test from command line:
curl -X OPTIONS https://api.medsync.app/api/v1/auth/login \
  -H "Origin: https://app.medsync.app" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Look for response headers:
# < Access-Control-Allow-Origin: https://app.medsync.app
# < Access-Control-Allow-Methods: POST, OPTIONS
# < Access-Control-Allow-Headers: ...

# If missing, CORS is not configured correctly on backend
```

#### Step 4: Check NEXT_PUBLIC_API_URL

```bash
# Frontend must know where API is:
# .env in medsync-frontend/:
NEXT_PUBLIC_API_URL=https://api.medsync.app/api/v1

# If this doesn't match actual API URL, requests will fail
# Verify by checking in browser:
# - Open http://app.medsync.app
# - Go to Network tab
# - Look at API request URL
# - Should match NEXT_PUBLIC_API_URL
```

#### Step 5: Test Credentials are Sent

```javascript
// In browser, check if requests include credentials:
fetch('https://api.medsync.app/api/v1/auth/me', {
  credentials: 'include',  // ← Must include this
  headers: {
    'Authorization': 'Bearer <token>'
  }
})

// Without credentials: 'include', cookies and auth headers won't be sent
```

### Solution

**Option A: Fix CORS_ALLOWED_ORIGINS (Most Common)**

```bash
# 1. Identify your frontend domain:
#    Example: app.medsync.app or app.medsync.local

# 2. Update in deployment platform:
#    CORS_ALLOWED_ORIGINS=https://app.medsync.app,https://medsync-frontend-app.vercel.app

# 3. Include all potential frontend URLs:
#    - Production: https://app.medsync.app
#    - Vercel preview: https://medsync-frontend-app-*.vercel.app
#    - Staging: https://staging-app.medsync.app

# 4. Redeploy API

# 5. Clear browser cache (Ctrl+Shift+Delete) and reload
```

**Option B: Verify Frontend URL**

```bash
# 1. Check what URL frontend is actually served from:
#    - Open frontend in browser
#    - Check address bar: https://...
#    - This is the "origin" that needs to be in CORS_ALLOWED_ORIGINS

# 2. Verify frontend's NEXT_PUBLIC_API_URL:
#    - In medsync-frontend/.env (or Vercel env vars)
#    - Should point to your API domain: https://api.medsync.app/api/v1

# 3. If mismatch, update and redeploy
```

**Option C: Enable Credentials in API Requests**

```javascript
// In frontend API client (lib/api-client.ts), ensure:
const response = await fetch(url, {
  method: 'POST',
  credentials: 'include',  // ← Send cookies
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
});
```

**Option D: Temporary Testing (Development Only)**

```bash
# For development/testing, you can permit all origins:
# DO NOT USE IN PRODUCTION
CORS_ALLOWED_ORIGINS=*

# But this is a security risk. After testing, revert to specific domains.
```

### Prevention

- ✅ List all frontend domains in CORS_ALLOWED_ORIGINS
- ✅ Never use wildcard `*` in production
- ✅ Include `credentials: 'include'` in fetch requests
- ✅ Test CORS immediately after changing API domain
- ✅ Document approved CORS origins in deployment guide

---

## Issue 6: File Upload Size Limit Exceeded

### Symptoms

- Upload fails with "413 Payload Too Large" or "413 Request Entity Too Large"
- "File size exceeds maximum allowed" message in UI
- Large lab reports or imaging files cannot be uploaded
- Works for small files, fails for files >5MB

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| File exceeds Django limit | High | Upload rejected |
| File exceeds web server limit (Nginx/Vercel) | High | Upload rejected at proxy |
| Chunk size too small | Medium | Upload slow or fails |
| Disk space full | Low | Upload fails server-side |

### Diagnosis Steps

#### Step 1: Check File Size

```bash
# Get file size before uploading:
# Linux/macOS:
ls -lh filename.pdf
# Output: -rw-r--r-- 1 user staff 150M filename.pdf

# Windows PowerShell:
(Get-Item filename.pdf).Length
# Output: 157286400 bytes (~150 MB)

# Common limits:
# - Default Django: 2.5 MB per file
# - Typical production: 25-100 MB
# - Large files (MRI, radiology): 500 MB - 2 GB
```

#### Step 2: Check Django Configuration

```bash
# Django file size limits are set in settings.py:
# FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB

# Check in environment:
# Django allows per-endpoint override via:
# DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB

# Verify in deployment:
# Should be set to handle expected radiology/lab file sizes
```

#### Step 3: Check Web Server Limits

For Vercel:

```
Vercel limits: 4.5 MB for API requests (limit cannot be increased)
For larger files, must use:
- Direct upload to cloud storage (S3, GCS)
- Chunked upload with multipart
- Or hosted separately (HIPAA-compliant storage)
```

For Railway:

```bash
# Nginx/Gunicorn limits can be adjusted:
client_max_body_size 100M;  # In Nginx config

# Check current limit:
nginx -T | grep client_max_body_size
```

#### Step 4: Test Upload Endpoint

```bash
# Create test file:
dd if=/dev/zero of=test_10mb.bin bs=1M count=10

# Test upload:
curl -X POST https://api.medsync.app/api/v1/lab/attachments/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@test_10mb.bin" \
  -F "lab_order_id=<uuid>" \
  -v

# Expected responses:
# 200: Upload successful
# 413: File too large (limit exceeded)
# 400: Missing lab_order_id or other validation
```

### Solution

**Option A: Increase Django File Upload Limit**

```bash
# In deployment environment, set:
DATA_UPLOAD_MAX_MEMORY_SIZE=104857600  # 100 MB
FILE_UPLOAD_MAX_MEMORY_SIZE=104857600  # 100 MB

# If using Railway, also check:
# gunicorn settings: --limit-request-line 8190 --limit-request-fields 32000

# Redeploy application
```

**Option B: Implement Chunked Upload**

For very large files (>100 MB), use chunked/multipart upload:

```javascript
// Frontend chunked upload
const chunkSize = 5 * 1024 * 1024; // 5 MB chunks
const file = document.getElementById('fileInput').files[0];

for (let i = 0; i < file.size; i += chunkSize) {
  const chunk = file.slice(i, i + chunkSize);
  const formData = new FormData();
  formData.append('chunk', chunk);
  formData.append('chunk_number', i / chunkSize);
  formData.append('total_chunks', Math.ceil(file.size / chunkSize));
  
  await fetch('/api/v1/lab/attachments/upload-chunk', {
    method: 'POST',
    body: formData
  });
}
```

**Option C: Use Cloud Storage (Recommended for HIPAA)**

For healthcare data, use HIPAA-compliant cloud storage:

```bash
# Store files in S3 with encryption
# Configure in environment:
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_STORAGE_BUCKET_NAME=medsync-prod-files
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=files.medsync.app
AWS_S3_SIGNATURE_VERSION=s3v4
AWS_S3_ADDRESSING_STYLE=virtual
AWS_DEFAULT_ACL=private
AWS_S3_ENCRYPTION=AES256

# In Django settings:
STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    }
}
```

**Option D: Verify Disk Space**

```bash
# Check if server is out of disk space:
# On deployment server:
df -h

# Look for 100% usage:
# /dev/sda1       500G  500G    0 100% /

# If full, archive old files or delete temporary uploads:
find /tmp -type f -mtime +7 -delete  # Delete files >7 days old
```

### Prevention

- ✅ Set FILE_UPLOAD_MAX_MEMORY_SIZE to 50-100 MB for medical files
- ✅ Use cloud storage (S3) for large files to avoid server disk usage
- ✅ Implement chunked upload for files >50 MB
- ✅ Validate file size before upload (frontend UX)
- ✅ Archive old uploads monthly to manage disk space

---

## Issue 7: Email Not Sending

### Symptoms

- MFA codes not arriving via email
- Password reset emails not received
- "Email sending failed" error in logs (if shown)
- User can't complete MFA (must use backup code or TOTP)
- Password reset link doesn't arrive

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| SMTP credentials wrong | High | All emails fail |
| Email service rate-limited | Medium | Sporadic failures |
| Email provider account disabled | Low | All emails fail |
| DNS/SPF/DKIM misconfigured | Low | Emails marked as spam |
| Invalid recipient email | Medium | Single email fails |

### Diagnosis Steps

#### Step 1: Check Email Configuration

```bash
# Verify email settings in deployment environment:
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<SendGrid API key or password>
DEFAULT_FROM_EMAIL=MedSync <noreply@medsync.app>

# Common providers:
# - SendGrid: smtp.sendgrid.net:587
# - Mailgun: smtp.mailgun.org:587
# - Gmail: smtp.gmail.com:587 (use App Password, not account password)
# - AWS SES: email-smtp.region.amazonaws.com:587
```

#### Step 2: Test SMTP Connection Manually

```bash
# Using telnet (if available):
telnet smtp.sendgrid.net 587

# Expected response:
# 220 SG.sendgrid.net ESMTP ready

# Type commands:
EHLO medsync.app
AUTH LOGIN
<base64-encoded-username>
<base64-encoded-password>
QUIT
```

Or use Python:

```python
import smtplib
from email.mime.text import MIMEText

# Replace with your credentials
sender = "noreply@medsync.app"
recipient = "test@medsync.app"

try:
    server = smtplib.SMTP("smtp.sendgrid.net", 587)
    server.starttls()
    server.login("apikey", "<SendGrid API key>")
    
    msg = MIMEText("Test email")
    msg['Subject'] = "Test"
    msg['From'] = sender
    msg['To'] = recipient
    
    server.send_message(msg)
    print("✓ Email sent successfully")
except Exception as e:
    print(f"✗ Email failed: {e}")
finally:
    server.quit()
```

#### Step 3: Check SendGrid (or Email Provider) Account

```bash
# For SendGrid:
# 1. Log in to https://app.sendgrid.com
# 2. Go to Settings → API Keys
# 3. Verify API key is active
# 4. Check Sender Authentication → Verify Domain SPF/DKIM records

# Check if account has email credits:
# 1. Go to Plan & Billing → Current Plan
# 2. Verify plan is active (not "Free - All Sent")
# 3. Check sending capacity

# Check recent sending activity:
# 1. Go to Email Activity
# 2. Look for any recent emails from your sender address
# 3. If none, SMTP may not be configured
```

#### Step 4: Check Django Email Logs

```bash
# Django logs email sending attempts:
# Check application logs in deployment platform

# For console logging (development):
# In settings.py:
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    # Prints emails to console instead of sending

# For file logging:
# Set: EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
# And: EMAIL_FILE_PATH = '/tmp/app-messages'
# Then: cat /tmp/app-messages to view sent emails

# In production, check logs:
# Railway: railway logs | grep -i email
# Vercel: vercel logs api
```

#### Step 5: Test Email Endpoint Directly

```bash
# In Django shell:
python manage.py shell

from django.core.mail import send_mail

send_mail(
    subject='Test Email',
    message='This is a test',
    from_email='noreply@medsync.app',
    recipient_list=['youremail@example.com'],
)

# Should print "1" if successful
# Should print exception if failed
```

### Solution

**Option A: Fix SMTP Credentials (Most Common)**

```bash
# 1. Verify credentials:
#    - Check EMAIL_HOST (smtp.sendgrid.net for SendGrid)
#    - Check EMAIL_PORT (587 for TLS, 465 for SSL)
#    - Check EMAIL_HOST_USER (usually "apikey" for SendGrid)
#    - Check EMAIL_HOST_PASSWORD (API key, not account password)

# 2. Update in deployment platform:
#    Railway: Settings → Variables → update EMAIL_* variables
#    Vercel: Settings → Environment Variables → update EMAIL_* variables

# 3. Redeploy application

# 4. Test: Trigger password reset in UI, check email
```

**Option B: Update SendGrid API Key**

```bash
# If API key is invalid/expired:
# 1. Log in to SendGrid dashboard
# 2. Settings → API Keys → Create New Key (Restricted Access)
# 3. Copy new key
# 4. Update EMAIL_HOST_PASSWORD in deployment
# 5. Redeploy and test
```

**Option C: Use Development Email Backend (Temporary)**

```bash
# For development only, print emails to logs:
# Set: EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Emails will print to console instead of sending
# Good for testing without email account

# But remove before production!
```

**Option D: Configure SPF/DKIM (If Emails Go to Spam)**

```
If emails arrive in spam folder:

1. In SendGrid dashboard, go to Settings → Sender Authentication
2. Add your domain (e.g., medsync.app)
3. Add SPF record to your DNS:
   v=spf1 sendgrid.net ~all

4. Add DKIM record to your DNS:
   (SendGrid provides exact record to add)

5. Wait 24 hours for DNS propagation
6. Verify in SendGrid dashboard
7. Retry sending emails
```

### Prevention

- ✅ Test SMTP connection immediately after setting up credentials
- ✅ Monitor SendGrid account for API key expiration
- ✅ Configure SPF/DKIM records for your domain
- ✅ Set up forwarding to admin email for critical notifications
- ✅ Log all email sending attempts for debugging

---

## Issue 8: Superuser Account Locked

### Symptoms

- Superuser cannot log in after MFA attempts
- "Account locked due to too many failed attempts" error
- Only error: "Try again after 1 hour"
- Hospital admin account unexpectedly locked

### Root Causes

| Cause | Likelihood | Impact |
|-------|------------|--------|
| 10+ failed MFA attempts in 1 hour | High | Account auto-locked for 1 hour |
| Brute-force attack detected | High | Multiple accounts locked |
| User forgot TOTP/backup codes | High | Multiple failed attempts |
| MFA not configured on device | Medium | Can't generate valid code |

### Diagnosis Steps

#### Step 1: Verify Account Lock Status

```bash
# Connect to database:
psql $DATABASE_URL

# Check lock status:
SELECT email, account_status, locked_until FROM core_user 
WHERE email='superadmin@medsync.gh';

# Output:
# email              | account_status | locked_until
# superadmin@medsync.gh | active       | 2024-12-20 15:30:00

# If locked_until > NOW(), account is locked
# If locked_until < NOW(), lock has expired (user can retry)
# If locked_until IS NULL, account is not locked
```

#### Step 2: Check Failed Login Attempts

```bash
# In same psql session:
SELECT COUNT(*) FROM core_auditlog 
WHERE user_id=(SELECT id FROM core_user WHERE email='superadmin@medsync.gh')
  AND action='MFA_FAILED'
  AND timestamp > NOW() - INTERVAL '1 hour';

# If count >= 10, account was locked

# View recent attempts:
SELECT timestamp, action, ip_address FROM core_auditlog 
WHERE user_id=(SELECT id FROM core_user WHERE email='superadmin@medsync.gh')
  AND action IN ('MFA_FAILED', 'LOGIN_FAILED')
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 10;
```

#### Step 3: Check for Brute-Force Attack

```bash
# If multiple accounts locked from same IP, likely attack:
SELECT DISTINCT(ip_address), COUNT(*) as failures FROM core_auditlog 
WHERE action='MFA_FAILED'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
ORDER BY failures DESC;

# If single IP has >50 failures, it's likely a brute-force attempt
```

### Solution

**Option A: Manually Unlock Account (Immediate)**

```bash
# In psql:
psql $DATABASE_URL

# Unlock the superuser account:
UPDATE core_user 
SET locked_until=NULL 
WHERE email='superadmin@medsync.gh';

# Verify:
SELECT locked_until FROM core_user WHERE email='superadmin@medsync.gh';
# Should show NULL or empty

# Exit psql:
\q

# Superuser can now log in again
```

**Option B: Reset MFA for Superuser**

```bash
# If user forgot TOTP or backup codes:
# Using API (requires another admin):

curl -X POST https://api.medsync.app/api/v1/admin/users/<superuser-uuid>/reset-mfa \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{}'

# Or in database:
psql $DATABASE_URL

SELECT id FROM core_user WHERE email='superadmin@medsync.gh';
# Note the UUID

DELETE FROM otp_totp_device 
WHERE user_id='<superuser-uuid>';

DELETE FROM core_backupcode 
WHERE user_id='<superuser-uuid>';

\q

# Superuser must set up MFA again on next login
```

**Option C: Block Brute-Force IP (If Under Attack)**

```bash
# If many failed attempts from same IP:

# Get the attacking IP:
SELECT ip_address, COUNT(*) FROM core_auditlog 
WHERE action='MFA_FAILED'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
ORDER BY COUNT(*) DESC
LIMIT 1;

# Block in firewall (example with iptables):
sudo iptables -A INPUT -s <attacking-ip> -j DROP

# Or in your cloud provider's firewall:
# - AWS: Security Groups → add deny rule for IP
# - Railway: may not have IP-level blocking (use rate-limiting instead)
# - Vercel: similar firewall rules available

# Monitor for similar attack patterns:
SELECT ip_address, COUNT(*) FROM core_auditlog 
WHERE action IN ('MFA_FAILED', 'LOGIN_FAILED')
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY ip_address
ORDER BY COUNT(*) DESC
LIMIT 10;
```

**Option D: Wait for Auto-Unlock (1 Hour)**

```
If you can't access database and need to wait:

1. Lock duration: 1 hour from first failed attempt
2. User can retry after lock expires
3. Meanwhile, use another superuser account if available
4. Or contact someone with database access to unlock manually
```

### Prevention

- ✅ Save backup codes in secure location during MFA setup
- ✅ Enable account lockout after 10 failed MFA attempts (already in MedSync)
- ✅ Implement rate limiting on login endpoint (already configured)
- ✅ Monitor audit logs for suspicious activity
- ✅ Maintain list of hospital admins who can unlock accounts
- ✅ Have recovery procedure documented and tested

---

## Quick Reference Troubleshooting Flowchart

```
Is the API responding?
├─ YES → Health check shows "healthy"
│        └─ Is user authenticated?
│           ├─ YES → Can access patient records?
│           │        ├─ YES → System working! Check specific feature
│           │        └─ NO → Issue #5 (CORS) or #4 (WebAuthn)
│           └─ NO → Go to Issue #2 (JWT) or #3 (TOTP)
│
└─ NO → Health check fails
        └─ Is database connected?
           ├─ YES → Check logs for errors
           └─ NO → Issue #1 (Database Connection)
```

---

## Support Resources

| Topic | Resource |
|-------|----------|
| **Django Errors** | `medsync-backend/api/` logs |
| **Database Issues** | Neon console: https://console.neon.tech |
| **Deployment Logs** | Railway: `railway logs` or Vercel: `vercel logs api` |
| **API Documentation** | `docs/API_REFERENCE.md` |
| **Deployment Guide** | `docs/DEPLOYMENT.md` |
| **GitHub Issues** | https://github.com/kaacquah2/EMR/issues |

---

## Escalation Path

1. **Try troubleshooting steps** in this guide
2. **Check logs** in deployment platform
3. **Consult API_REFERENCE.md** and DEPLOYMENT.md
4. **Contact system administrator** with:
   - Error message (exact text)
   - Time of occurrence
   - Affected user/endpoint
   - Steps to reproduce
5. **File GitHub issue** if bug confirmed
6. **Contact support** if infrastructure-level issue

Remember: **Always backup data before making changes to production systems.**
