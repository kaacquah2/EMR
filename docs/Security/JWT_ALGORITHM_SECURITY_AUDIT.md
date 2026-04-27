# 🚨 CRITICAL SECURITY ISSUE: JWT Signing Algorithm Mismatch

**Severity**: 🔴 **CRITICAL** - Token Forgery Risk  
**Issue**: HS256 vs RS256 mismatch for cross-hospital consent tokens  
**Status**: INVESTIGATION & REMEDIATION REQUIRED  
**Date**: April 19, 2026

---

## Executive Summary

**Current State**: ❌ **SECURITY RISK IDENTIFIED**

The documentation states `HS256` for all JWT operations, but cross-hospital X-Consent-Token usage **REQUIRES RS256** (asymmetric signing). Using HS256 for cross-hospital tokens would allow receiving hospitals to forge consent tokens if they know the shared secret.

**The Problem**:
- **HS256 (HMAC)**: Symmetric key - both parties have the same secret
  - ✅ Safe for: Single-origin tokens (your backend signs & verifies)
  - ❌ UNSAFE for: Multi-party verification (any party with secret can forge)

- **RS256 (RSA)**: Asymmetric key pair - private key for signing, public key for verification
  - ✅ REQUIRED for: Cross-hospital scenarios where verifier must not be able to forge

---

## Issue Details

### What ARCHITECTURE.md Currently States

```
- **JWT Library:** `djangorestframework-simplejwt` with HS256 signing
```

### What Implementation Actually Shows

**Backend settings.py (Line 337-342)**:
```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=_jwt_access_minutes()),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_jwt_refresh_days()),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

**No explicit algorithm configuration** → Defaults to HS256

### What Should Happen (Cross-Hospital Scenario)

**Scenario**: Hospital A wants to send a consent token to Hospital B

```
Hospital A (Central Platform):
  ✓ Has PRIVATE KEY
  ✓ Can sign consent tokens with RS256
  
Hospital B (Receiving):
  ✓ Has PUBLIC KEY
  ✓ Can verify but CANNOT forge signatures
  ✓ Cannot sign new tokens (no private key)
```

**If HS256 is used instead**:
```
Hospital A: SECRET_KEY = "abc123"
Hospital B: SECRET_KEY = "abc123"  (same secret!)
  ✓ Can verify tokens
  ✗ Can also FORGE new tokens (they know the secret!)
  ✗ Can impersonate consent from Hospital A
```

---

## Attack Scenario

### How a Malicious Hospital Could Exploit HS256

```
1. Hospital B learns the HS256 secret (theft, supply chain, insider)

2. Hospital B forges a consent token:
   payload = {
     "global_patient_id": "<victim_id>",
     "from_facility": "hospital_a_id",
     "to_facility": "hospital_b_id",
     "scope": "FULL_RECORD",
     "expires": "<far_future>"
   }
   signature = HMAC_SHA256(payload, known_secret)

3. Hospital B uses this token to access any patient record from Hospital A

4. No way for Hospital A to detect the forgery
   (Both tokens have valid HS256 signatures)
```

---

## Current Implementation Assessment

### What's Working (HS256 is fine for these):

✅ **Regular JWT Access Tokens** (single backend)
  - Patient login → backend signs access token with HS256
  - Patient sends token → backend verifies with same HS256 secret
  - ✅ Safe because only one party (central backend) has the secret

✅ **Token Refresh** (single backend)
  - Refresh endpoint signs new token → backend verifies
  - ✅ Safe for same reason

### What's NOT Safe (if X-Consent-Token exists):

❌ **X-Consent-Token for Cross-Hospital** (multiple backends)
  - If Hospital A sends consent token to Hospital B
  - Hospital B needs to verify but NOT forge
  - ❌ HS256 is UNSAFE - Hospital B could forge with known secret

---

## Finding: X-Consent-Token Implementation Status

### Search Results

**In `can_access_cross_facility()` function** (api/utils.py):
- ✅ Checks `Consent.objects.filter()` in database
- ✅ Checks `Referral.objects.filter()` in database
- ✅ Checks `BreakGlassLog.objects.filter()` in database
- ❌ **NO X-Consent-Token implementation found**

**Conclusion**: Currently, cross-facility access is verified via database queries, not JWT tokens. This is actually **safer** than using HS256 tokens, but:

1. **If X-Consent-Token is added later**, it MUST use RS256
2. **Documentation incorrectly states HS256** as the algorithm
3. **Code currently doesn't explicitly configure algorithm** → defaults to HS256

---

## Findings vs. Requirements

### What Was Planned vs. What's Implemented

| Component | Planned | Implemented | Status |
|-----------|---------|-------------|--------|
| Regular JWT (access token) | HS256 | HS256 | ✅ OK |
| Token Refresh | HS256 | HS256 | ✅ OK |
| X-Consent-Token | RS256 | Not found | ⚠️ N/A |
| Cross-facility verification | RS256 tokens | Database queries | ✅ SAFER |
| Algorithm config | Explicit in settings | Not found (default HS256) | ⚠️ UNDOCUMENTED |

---

## Required Remediations

### 1. IMMEDIATE: Document Current Architecture ✅

Create clear documentation of what is actually deployed:

**File**: `JWT_ALGORITHM_AUDIT.md`

```markdown
# JWT Algorithm & Cross-Facility Token Security

## Current Implementation

### Regular JWT (Access & Refresh)
- **Algorithm**: HS256 (HMAC-SHA256)
- **Signing**: Django SIMPLE_JWT (default)
- **Usage**: Single-backend verification
- **Security**: ✅ SAFE (only backend knows secret)

### Cross-Facility Consent
- **Current**: Database lookup (Consent model)
- **Algorithm**: N/A (no JWT tokens used)
- **Security**: ✅ SAFE (backend enforces access)

### If X-Consent-Token Added (Future)
- **MUST USE**: RS256 (RSA-SHA256)
- **Why**: Receiving hospital verifies but cannot forge
- **Configuration**: Set SIMPLE_JWT["ALGORITHM"] = "RS256"
- **Key Management**: Use asymmetric key pair, distribute public key to hospitals
```

### 2. MEDIUM PRIORITY: Explicitly Configure Algorithm

**File**: `medsync-backend/medsync_backend/settings.py`

Add explicit algorithm configuration:

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=_jwt_access_minutes()),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_jwt_refresh_days()),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",  # ✅ EXPLICIT - single-backend tokens only
}
```

### 3. FUTURE: If X-Consent-Token Is Needed

Create separate RS256 configuration:

```python
# For cross-hospital consent tokens (if implemented)
X_CONSENT_TOKEN_CONFIG = {
    "algorithm": "RS256",  # ✅ MUST be asymmetric
    "private_key_path": config("X_CONSENT_PRIVATE_KEY_PATH", default=None),
    "public_key_distribution": config("X_CONSENT_PUBLIC_KEY_ENDPOINT", default=None),
}
```

### 4. Update ARCHITECTURE.md

**Section**: Authentication Flow → JWT Algorithms

```markdown
## JWT Algorithms

### Regular Access/Refresh Tokens
- **Algorithm**: HS256 (HMAC-SHA256)
- **Security Model**: Symmetric key (only backend has secret)
- **Use Case**: Single-origin authentication
- **Status**: ✅ Deployed

### Cross-Hospital Consent Tokens (Future)
- **Algorithm**: RS256 (RSA-SHA256) ← REQUIRED
- **Security Model**: Asymmetric key pair
- **Why RS256**: Receiving hospital verifies but cannot forge
- **Status**: ❌ Not yet implemented

### Current Cross-Facility Access
- **Method**: Database queries with consent/referral/break-glass checks
- **Security**: ✅ Backend-enforced, no token forgery risk
- **Status**: ✅ Deployed
```

---

## Testing Recommendations

### Test 1: Verify Algorithm in Use

```python
# File: api/tests/test_jwt_algorithm.py

def test_jwt_algorithm_is_hs256():
    """Verify that regular JWT tokens use HS256."""
    from rest_framework_simplejwt.settings import api_settings
    
    algorithm = api_settings.ALGORITHM
    assert algorithm == "HS256", f"Expected HS256, got {algorithm}"
```

### Test 2: Cross-Facility Doesn't Use JWT Tokens

```python
def test_cross_facility_uses_database_not_tokens():
    """Verify cross-facility access checks database, not JWT tokens."""
    from api.utils import can_access_cross_facility
    
    # Create consent in database
    consent = Consent.objects.create(
        from_facility=hospital_a,
        to_facility=hospital_b,
        patient=patient,
        scope="FULL_RECORD"
    )
    
    # Access should work via database check
    allowed, scope = can_access_cross_facility(doctor_b, patient.global_id)
    assert allowed and scope == "FULL_RECORD"
```

### Test 3: If X-Consent-Token Is Added, Verify RS256

```python
def test_x_consent_token_uses_rs256():
    """If X-Consent-Token is implemented, it MUST use RS256."""
    # Future test when X-Consent-Token is added
    # Should verify:
    # 1. Algorithm is RS256 (not HS256)
    # 2. Receiving hospital cannot forge signatures
    # 3. Private key is never distributed
    pass
```

---

## Risk Assessment

### Current State

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **HS256 for cross-hospital** | 🟡 Medium | 🔴 Critical | Not implemented (using DB queries) |
| **Algorithm not explicit** | 🟢 Low | 🟡 Medium | Add explicit config |
| **Documentation misleading** | 🟢 Low | 🟡 Medium | Update ARCHITECTURE.md |
| **Future X-Consent-Token adds HS256** | 🟡 Medium | 🔴 Critical | Define RS256 requirement now |

### Current Implementation is Actually Safer

The fact that **X-Consent-Token is not implemented** means the system currently uses database queries for cross-facility access verification. This is actually **more secure** than JWT tokens would be:

✅ **Database verification**:
- Checked on every access
- Cannot be replayed
- Immediately invalidated on revocation
- Backend has full authority

❌ **JWT tokens** (if used with HS256):
- Forgeable if secret is known
- Replayed until expiration
- Hard to revoke
- Subject to Man-in-the-Middle if not HTTPS

---

## Recommendations Summary

### 🟢 GREEN: Safe to Deploy As-Is

✅ Regular JWT (HS256) for single-backend authentication is safe  
✅ Cross-facility access via database queries is safe  
✅ No X-Consent-Token implemented to introduce HS256 risk  

### 🟡 YELLOW: Minor Issues to Address

⚠️ Algorithm not explicitly configured in settings (add explicit `ALGORITHM: HS256`)  
⚠️ Documentation misleading (update ARCHITECTURE.md)  
⚠️ No test verifying algorithm in use (add test)  

### 🔴 RED: Must Do Before Any Cross-Hospital JWT Tokens

❌ If X-Consent-Token is added, it MUST use RS256  
❌ Create key pair management strategy  
❌ Define public key distribution mechanism  
❌ Document asymmetric key rotation  

---

## Action Items

| Priority | Item | Owner | Timeline |
|----------|------|-------|----------|
| 🔴 NOW | Explicitly configure ALGORITHM in settings.py | Backend Team | Today |
| 🔴 NOW | Update ARCHITECTURE.md with algorithm details | Docs Team | Today |
| 🟡 SOON | Add test_jwt_algorithm.py verification test | QA Team | This week |
| 🟡 SOON | Create JWT_ALGORITHM_AUDIT.md documentation | Docs Team | This week |
| 🟢 FUTURE | Define RS256 strategy for X-Consent-Token (if needed) | Architecture | When needed |

---

## Files to Create/Update

### 1. Create: `JWT_ALGORITHM_AUDIT.md`

Document the algorithm usage and security model.

### 2. Update: `docs/ARCHITECTURE.md`

Add explicit section on JWT algorithms and security model.

### 3. Update: `medsync-backend/medsync_backend/settings.py`

Add explicit `ALGORITHM` configuration to SIMPLE_JWT.

### 4. Create: `api/tests/test_jwt_algorithm.py`

Test that algorithms are configured correctly.

---

## Conclusion

**Current Risk Level**: 🟢 **LOW** (X-Consent-Token not implemented; DB queries used instead)

**If X-Consent-Token Added**: 🔴 **CRITICAL** (Must use RS256, not HS256)

**Recommendation**: 
1. ✅ Safe to deploy current implementation
2. ✅ Add explicit algorithm configuration for documentation
3. ✅ Update architecture docs for clarity
4. ⚠️ Require RS256 review before any cross-hospital JWT tokens are added

---

**Security Audit**: PASSED (with recommendations)  
**Deployment Approval**: ✅ YES (with documentation updates)  
**Risk Mitigation**: DOCUMENTED & PREVENTIVE

