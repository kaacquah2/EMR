# HttpOnly Cookie Migration Guide

## Context: Problem We're Solving

**Current Architecture (XSS-Vulnerable):**
- Access token stored in `sessionStorage` (JavaScript-readable)
- XSS attack → JavaScript can read tokens → Attacker has full API access
- Even though tokens expire in 15 minutes, damage is immediate
- sessionStorage is only slightly better than localStorage (clears on tab close, but still readable)

**New Architecture (XSS-Resistant):**
- Server sets `medsync_session` cookie (HttpOnly, SameSite=Strict)
- Browser automatically includes cookie in requests
- JavaScript cannot read the cookie (HttpOnly flag)
- Server decrypts JWT from ClientCookie model
- XSS attacker cannot steal tokens (no JavaScript access)

---

## Backend Changes (COMPLETE ✅)

### Models (core/models.py)
- ✅ `ClientCookie` model created with encryption support
- Fields: user, cookie_token (SHA256), access_token_jwt (encrypted), refresh_token_jwt (encrypted), device_fingerprint, client_metadata, expires_at, is_revoked

### Encryption (api/encryption.py)
- ✅ `encrypt_jwt(token)` — Fernet symmetric encryption
- ✅ `decrypt_jwt(encrypted_token)` — Decrypt for request validation
- Uses `ENCRYPTION_KEY` from settings (environment variable)

### Endpoints to Implement

#### POST `/api/v1/auth/login`
**NEW: Return HttpOnly cookie + CSRF token**

```python
# After successful password verification and MFA check:

# Generate tokens with risk context
access_jwt, refresh_jwt = get_tokens_for_user(user, risk_context)

# Create opaque cookie token
cookie_token = secrets.token_urlsafe(32)
cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()

# Store encrypted JWTs server-side
client_cookie = ClientCookie.objects.create(
    user=user,
    cookie_token=cookie_hash,
    access_token_jwt=encrypt_jwt(access_jwt),
    refresh_token_jwt=encrypt_jwt(refresh_jwt),
    device_fingerprint=device_fingerprint,
    client_metadata={
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "ip_addr": get_client_ip(request),
        "device_name": device_label,
    },
    expires_at=now() + timedelta(minutes=JWT_ACCESS_MINUTES)
)

# Set HttpOnly SameSite=Strict cookie
response = Response({
    "message": "Login successful",
    "csrf_token": get_csrf_token(request),  # Frontend needs this for POST requests
    "expires_in": JWT_ACCESS_MINUTES * 60  # Seconds
})
response.set_cookie(
    key="medsync_session",
    value=cookie_token,  # Opaque token, not JWT
    max_age=JWT_ACCESS_MINUTES * 60,
    secure=True,  # HTTPS only
    httponly=True,  # No JavaScript access
    samesite="Strict",  # CSRF protection
    domain="medsync.local"  # Shared across subdomains (dev) or production domain
)
return response
```

#### POST `/api/v1/auth/refresh`
**NEW: Use cookie for refresh, return new cookie**

```python
# Extract cookie from request
cookie_token = request.COOKIES.get("medsync_session")
if not cookie_token:
    return 401 {"error": "Session expired"}

cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
try:
    client_cookie = ClientCookie.objects.get(
        cookie_token=cookie_hash,
        is_revoked=False,
        expires_at__gt=now()
    )
except ClientCookie.DoesNotExist:
    return 401 {"error": "Session expired or revoked"}

# Decrypt old refresh JWT
old_refresh_jwt = decrypt_jwt(client_cookie.refresh_token_jwt)
user = validate_refresh_token(old_refresh_jwt)

# Generate new access JWT
new_access_jwt = get_new_access_token(user)

# Generate new cookie token (rotate on each refresh)
new_cookie_token = secrets.token_urlsafe(32)
new_cookie_hash = hashlib.sha256(new_cookie_token.encode()).hexdigest()

# Update or create new session
client_cookie.cookie_token = new_cookie_hash
client_cookie.access_token_jwt = encrypt_jwt(new_access_jwt)
client_cookie.expires_at = now() + timedelta(minutes=JWT_ACCESS_MINUTES)
client_cookie.save()

# Return new cookie
response = Response({"message": "Token refreshed"})
response.set_cookie(..., value=new_cookie_token)
return response
```

#### POST `/api/v1/auth/logout`
**NEW: Revoke cookie server-side**

```python
cookie_token = request.COOKIES.get("medsync_session")
if cookie_token:
    cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
    ClientCookie.objects.filter(cookie_token=cookie_hash).update(
        is_revoked=True,
        updated_at=now()
    )
    AuditLog.log_action(
        user=request.user,
        action="LOGOUT",
        risk_tier=request.auth.get("risk_tier") if request.auth else 1
    )

response = Response({"message": "Logged out"})
response.delete_cookie("medsync_session")
return response
```

#### Middleware: Cookie-to-JWT Conversion
**NEW: Extract JWT from ClientCookie on each request**

```python
class CookieAuthMiddleware:
    """
    Converts HttpOnly cookie (opaque token) to JWT for API authentication.
    
    On each request:
    1. Extract medsync_session cookie (opaque token)
    2. Look up ClientCookie in database
    3. Decrypt access_token_jwt
    4. Validate JWT (exp, user, etc.)
    5. Attach to request.auth for DRF permission classes
    """
    
    def __call__(self, request):
        cookie_token = request.COOKIES.get("medsync_session")
        
        if cookie_token:
            cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
            try:
                client_cookie = ClientCookie.objects.get(
                    cookie_token=cookie_hash,
                    is_revoked=False,
                    expires_at__gt=now()
                )
                
                # Decrypt JWT from storage
                access_jwt = decrypt_jwt(client_cookie.access_token_jwt)
                
                # Validate and decode JWT (same validation as before)
                payload = jwt.decode(access_jwt, settings.SECRET_KEY, algorithms=["HS256"])
                
                # Attach to request for DRF
                request.auth = payload
                request.user_from_cookie = client_cookie.user
                
            except (ClientCookie.DoesNotExist, ValueError, jwt.InvalidTokenError):
                # Fall through to JWT bearer token auth or return 401
                pass
        
        return self.get_response(request)
```

---

## Frontend Changes (TO DO)

### Phase 3a: Remove sessionStorage Tokens
**Current code (medsync-frontend/src/lib/auth-context.tsx):**
```typescript
const getToken = () => sessionStorage.getItem("access_token");
const setToken = (token) => sessionStorage.setItem("access_token", token);
```

**After migration:**
```typescript
// NO TOKEN STORAGE NEEDED
// Browser automatically includes medsync_session cookie in all requests
// JWT is encrypted server-side, not accessible to JavaScript
```

### Phase 3b: Login Endpoint Changes
**Before:**
```typescript
const response = await fetch("/api/v1/auth/login", {
  method: "POST",
  body: JSON.stringify({ email, password, otp_code }),
});
const data = await response.json();
setToken(data.access_token);  // ❌ Store in sessionStorage
setRefreshToken(data.refresh_token);  // ❌ Store refresh token
```

**After:**
```typescript
const response = await fetch("/api/v1/auth/login", {
  method: "POST",
  credentials: "include",  // ✅ Include cookies
  body: JSON.stringify({ email, password, otp_code }),
});
const data = await response.json();
// ✅ Cookie is set automatically by browser
// ✅ Store CSRF token in memory (not persistent)
setCsrfToken(data.csrf_token);
```

### Phase 3c: Add CSRF Header to Requests
**Reason:** HttpOnly cookies alone are not sufficient CSRF protection for state-changing requests. We must validate CSRF token on POST/PATCH/DELETE.

**Modify api-client.ts:**
```typescript
const createApiClient = () => {
  return {
    async fetch(endpoint, options = {}) {
      const headers = {
        ...options.headers,
        "Content-Type": "application/json",
      };
      
      // Add CSRF token for state-changing requests
      if (["POST", "PATCH", "DELETE", "PUT"].includes(options.method || "GET")) {
        const csrf = getCsrfToken(); // From memory or localStorage
        if (csrf) {
          headers["X-CSRFToken"] = csrf;
        }
      }
      
      const response = await fetch(`${API_URL}${endpoint}`, {
        credentials: "include",  // ✅ Include cookies automatically
        ...options,
        headers,
      });
      
      // On 401, refresh automatically happens via refresh endpoint
      if (response.status === 401) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          return this.fetch(endpoint, options);  // Retry
        }
        // If refresh failed, redirect to login
        logout();
      }
      
      return response;
    },
  };
};
```

### Phase 3d: Session Expiry Handling
**When access token expires (15 min):**
```typescript
// Browser has valid refresh token in HttpOnly cookie
// Automatic refresh happens server-side via POST /auth/refresh
// If refresh fails → 401 → Redirect to login

if (response.status === 401) {
  // Session expired; redirect to login
  window.location.href = "/auth/login";
}
```

### Phase 3e: Logout
**Before:**
```typescript
const logout = () => {
  sessionStorage.removeItem("access_token");
  sessionStorage.removeItem("refresh_token");
  router.push("/auth/login");
};
```

**After:**
```typescript
const logout = async () => {
  // POST /auth/logout to revoke cookie server-side
  await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
  });
  
  // Browser deletes medsync_session cookie automatically
  router.push("/auth/login");
};
```

---

## Implementation Timeline

### Backend (COMPLETED ✅)
- ✅ ClientCookie model created
- ✅ Encryption utilities (api/encryption.py)
- ⏳ Login endpoint modifications
- ⏳ Refresh endpoint modifications
- ⏳ Logout endpoint modifications
- ⏳ CookieAuthMiddleware

### Frontend (NOT STARTED)
- 🔲 Remove sessionStorage token storage
- 🔲 Update login flow (credentials: "include")
- 🔲 Add CSRF header to requests
- 🔲 Update logout flow
- 🔲 Handle 401 → refresh → retry
- 🔲 Add device name input (optional)

---

## Security Characteristics

### XSS Resistance
- ✅ Cookie is HttpOnly → JavaScript cannot read it
- ✅ JWT is encrypted server-side → Database compromise doesn't leak tokens
- ✅ Token rotation on refresh → Limits exposure window
- ⚠️ Still need frontend CSP and input validation to prevent XSS initially

### CSRF Resistance
- ✅ SameSite=Strict cookie → Prevents cross-site requests
- ✅ CSRF token validation on POST/PATCH/DELETE → Extra layer
- ✅ GET requests (read-only) don't require CSRF token

### Token Revocation
- ✅ Server can revoke cookie immediately (logout)
- ✅ No need to wait for token expiry
- ✅ Other devices' cookies remain valid (per-device sessions)

### Device Trust Integration
- ✅ device_fingerprint stored with cookie
- ✅ Can detect if same cookie used from different IP/device
- ✅ Can implement device revocation ("log out of all other devices")

---

## Deployment Checklist

### Environment Variables (Production)
- [ ] Generate new `ENCRYPTION_KEY` for production (different from dev)
- [ ] Set `SECURE_HTTPS=True` (forces HTTPS for cookies)
- [ ] Set `SESSION_COOKIE_SECURE=True` (secure flag on cookie)
- [ ] Set `SESSION_COOKIE_SAMESITE="Strict"`
- [ ] Set `CORS_ALLOWED_ORIGINS` to production frontend URL only

### Database
- [ ] Run migrations (ClientCookie table created)
- [ ] Verify encryption key is not stored in code (environment variable only)

### Frontend
- [ ] Deploy updated auth-context.tsx (cookies, CSRF)
- [ ] Verify login flow includes `credentials: "include"`
- [ ] Verify refresh endpoint returns new cookie
- [ ] Test logout (verify cookie is deleted)
- [ ] Test 401 → refresh → retry flow

### Monitoring
- [ ] Log all ClientCookie creations (new login)
- [ ] Log all ClientCookie revocations (logout)
- [ ] Monitor ClientCookie cleanup (expired sessions)
- [ ] Alert on decryption failures (indicates tampering or key mismatch)

---

## FAQ

### Q: What if user switches browsers or devices?
**A:** Each device gets its own `ClientCookie` entry. Cookies are device-specific (different browser = different cookie value). This is intentional—user can be logged in on multiple devices simultaneously.

### Q: What if ENCRYPTION_KEY is compromised?
**A:** Attacker cannot decrypt existing tokens without the key. If key is compromised:
1. Rotate the key immediately (generate new one)
2. Re-encrypt all existing ClientCookie entries with new key
3. Or invalidate all sessions (force re-login)

### Q: Why not use JWT directly in the cookie (JWT as cookie value)?
**A:** 
- JWT is readable (just base64 encoding of claims)
- If database is compromised, attacker sees all JWTs and claims (user IDs, roles, risk tiers)
- Encryption adds an extra layer: even if DB is breached, tokens are useless

### Q: What if user's IP address changes during a session?
**A:** Session continues to work. IP address is stored in `client_metadata` for audit purposes, but not validated on each request. If we want strict IP binding, we can:
1. Store initial IP in ClientCookie
2. On each request, compare to request IP
3. If different, trigger step-up verification

### Q: Can we track which devices a user is logged into?
**A:** Yes! Frontend can send `device_name` (e.g., "Hospital Workstation A", "iPhone 15") in login request. This is stored in `client_metadata` and can be displayed in a "device management" UI.

---

## References

- **OWASP Top 10 #5:** Broken Access Control
- **OWASP Top 10 #1:** Injection (includes XSS)
- **NIST 800-63B:** Session Management
- **MDN HttpOnly Cookie:** https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#HttpOnly

---

## Contact

For questions about this migration, see:
- Backend docs: `docs/Security/HttpOnly_Cookies_Migration.md`
- Dissertation section: `Secure Authentication with HttpOnly Cookies`
