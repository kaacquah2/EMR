# MedSync Desktop-Only Deployment Guide

## Overview

MedSync is a **desktop-only clinical EMR system** optimized for healthcare staff using:
- **Windows laptops** with Windows Hello (fingerprint, face, PIN)
- **macBooks** with Touch ID or Face ID

Mobile devices (iOS, Android, Linux) are not supported and will receive clear guidance to use a desktop computer.

---

## 1. Platform Requirements

### Supported Platforms ✅
| Platform | Biometric Authentication | Status |
|----------|-------------------------|--------|
| **Windows 10+** | Windows Hello (fingerprint, face, PIN) | ✅ Fully Supported |
| **macOS 10.15+** | Touch ID or Face ID | ✅ Fully Supported |

### Unsupported Platforms ❌
| Platform | Reason | Guidance |
|----------|--------|----------|
| **iOS** | Clinical system requires desktop | Redirect to Windows/macOS |
| **Android** | Clinical system requires desktop | Redirect to Windows/macOS |
| **Linux** | Biometric support limited | Not supported in this deployment |
| **ChromeOS** | Not a primary deployment target | Not supported |

---

## 2. Authentication Architecture

### Desktop-Only Passkey Flow

```
User on Windows/macOS
        ↓
1. Enter email on login page
        ↓
2. Device platform validated (Windows/macOS only)
        ↓
3. Biometric prompt appears (Windows Hello / Touch ID / Face ID)
        ↓
4. Credential verified
        ↓
5. JWT tokens issued → Logged in! ✅
```

### Mobile Device Rejection (if accessed)

```
User on iPhone/Android
        ↓
1. Try to access MedSync
        ↓
2. Device validation fails
        ↓
3. Clear error message shown:
   "MedSync does not support mobile devices.
    Please use a Windows laptop or MacBook."
        ↓
4. Login blocked ❌
```

---

## 3. Implementation Details

### Backend Changes (Python/Django)

#### Platform Detection Function
```python
def _detect_platform(user_agent: str) -> str:
    """
    Detect platform from User-Agent.
    Returns: 'windows', 'macos', or 'unsupported'
    
    MedSync supports Windows and macOS only.
    """
    ua = (user_agent or "").lower()
    if 'windows' in ua:
        return 'windows'
    if 'macintosh' in ua or 'mac os x' in ua:
        return 'macos'
    return 'unsupported'  # iOS, Android, Linux, etc.
```

#### Passkey Registration Validation
```python
# In passkey_register_complete()
platform = _detect_platform(request.META.get('HTTP_USER_AGENT', ''))

if platform not in ('windows', 'macos'):
    return Response(
        {
            "message": "Passkey registration is only supported on Windows (Hello) "
                       "and macOS (Touch ID/Face ID)."
        },
        status=status.HTTP_403_FORBIDDEN,
    )
```

#### Authentication Endpoints Protection
- `POST /auth/passkey/auth/begin` - Desktop-only validation
- `POST /auth/passkey/auth/complete` - Desktop-only validation
- Both return **403 Forbidden** for mobile platforms with guidance

### Frontend Changes (React/TypeScript)

#### Device Policy Enforcement
New utility: `lib/device-policy.ts`
```typescript
export function validateDevicePolicy(): DevicePolicy {
  // Returns: { isSupported, platform, warning }
  // Checks User-Agent for Windows/macOS
  // Returns friendly error for unsupported platforms
}
```

#### Enhanced Passkey Detection
Updated: `lib/passkey.ts`
```typescript
function isSupportedPlatform(): boolean {
  const ua = navigator.userAgent.toLowerCase()
  return /windows|macintosh|mac os x/.test(ua)
}

export function isPasskeySupported(): boolean {
  return isSupportedPlatform() && 
         window.PublicKeyCredential !== undefined
}
```

#### Login Page Device Warning
Updated: `app/(auth)/login/page.tsx`
```tsx
{devicePolicy && !devicePolicy.isSupported && (
  <div className="bg-yellow-100 border border-yellow-300 rounded p-3">
    ⚠️ {devicePolicy.warning}
    <p>Supported: Windows (Hello) · macOS (Touch ID/Face ID)</p>
  </div>
)}
```

---

## 4. Error Messages & User Guidance

### User Sees on Mobile Device (Login Page)
```
⚠️ MedSync does not support iOS.
Please use a Windows laptop or MacBook to access MedSync.

Supported: Windows (Hello) · macOS (Touch ID/Face ID)
```

### User Sees on Mobile Device (Passkey Attempt)
```
MedSync does not support mobile devices.
Please use a Windows laptop or MacBook to sign in.
```

### User Sees on Android Device
```
⚠️ MedSync does not support Android.
Please use a Windows laptop or MacBook to access MedSync.

Supported: Windows (Hello) · macOS (Touch ID/Face ID)
```

---

## 5. Deployment Checklist

### Backend
- [x] Platform detection updated to support Windows/macOS only
- [x] Passkey registration validates platform (403 for mobile)
- [x] Passkey auth/begin validates platform (403 for mobile)
- [x] Passkey auth/complete validates platform (403 for mobile)
- [x] Audit logging includes platform information
- [x] Python code compiles without errors

### Frontend
- [x] Device policy utility created (`lib/device-policy.ts`)
- [x] Passkey support check includes platform validation
- [x] Login page displays device platform warning
- [x] Mobile device users get clear error messages
- [x] TypeScript types correctly typed
- [x] All changes compile without errors

### Documentation
- [x] This deployment guide created
- [x] Platform requirements documented
- [x] Error messages documented
- [x] Implementation details documented

---

## 6. Biometric Setup Instructions

### For Windows Users (Windows Hello)

1. **Check if Windows Hello is available:**
   - Settings → Accounts → Sign-in options
   - Look for "Windows Hello"

2. **Enable Windows Hello:**
   - Choose biometric type: Fingerprint, Face, or PIN
   - Follow setup wizard

3. **Register Passkey in MedSync:**
   - Click "Sign in with passkey" on login page
   - Place finger on reader or position face in camera
   - Confirm registration

### For macOS Users (Touch ID / Face ID)

1. **Check if biometric is available:**
   - System Preferences → Touch ID (or Face ID)
   - Verify your fingerprint or face is registered

2. **Set up MacBook biometric:**
   - Touch ID: Register fingerprints
   - Face ID: Position face for recognition

3. **Register Passkey in MedSync:**
   - Click "Sign in with passkey" on login page
   - Use Touch ID or Face ID when prompted
   - Confirm registration

---

## 7. Security Considerations

### Desktop-Only Benefits
- ✅ Full biometric support (platform authenticators)
- ✅ Better device management and MDM integration
- ✅ Stronger physical security in clinical settings
- ✅ Better screen sharing and privacy controls
- ✅ Offline capabilities more robust on desktops

### Access Control
- **Backend enforces**: Platform validation on every passkey request
- **Frontend validates**: Early rejection prevents unnecessary API calls
- **Clear messaging**: Users immediately understand requirements

### HTTPS Requirement (Production)
```typescript
// Enforced in device-policy.ts for production
if (isProduction && !isHttps) {
  // Block access, clinical data must be encrypted
}
```

---

## 8. Testing Desktop-Only Deployment

### Manual Testing
1. **Test on Windows with Windows Hello:**
   - [ ] Passkey button appears
   - [ ] Windows Hello prompt shows
   - [ ] Login successful

2. **Test on macOS with Touch ID:**
   - [ ] Passkey button appears
   - [ ] Touch ID prompt shows
   - [ ] Login successful

3. **Test mobile device rejection:**
   - [ ] iPhone: Device warning appears
   - [ ] Android: Device warning appears
   - [ ] Clear guidance to use desktop

### Automated Testing
```bash
# Check backend platform detection
pytest api/tests/test_auth.py::test_desktop_only_passkey -v

# Check frontend device policy validation
npm run test -- src/lib/device-policy.test.ts
```

---

## 9. Monitoring & Support

### What to Monitor
- Passkey registration success rate by platform
- Mobile device access attempts (should be 0 or minimal)
- Platform validation failures in logs

### Support Guidance
- **"I'm on my iPhone"** → Provide Windows/macBook instructions
- **"Passkey not working"** → Check device biometric is enabled
- **"Button doesn't appear"** → Likely unsupported device

### Logs to Check
```python
# Look for platform validation in audit logs
AuditLog.objects.filter(
    action='PASSKEY_REGISTERED',
    extra_data__platform='windows'  # or 'macos'
)

# Check rejected platforms
AuditLog.objects.filter(
    action='LOGIN_FAILED',
    reason='Unsupported platform'
)
```

---

## 10. Migration from Other Systems

If migrating from a system that supported mobile:
1. Communicate desktop-only requirement to all users
2. Provide Windows/macBook provisioning guidance
3. Phase out mobile device access gradually
4. Update IT policies to reflect desktop-only deployment
5. Document in IT onboarding procedures

---

## Appendix: HTTP User-Agent Examples

### Windows Detection
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36
```

### macOS Detection
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36
Mozilla/5.0 (Macintosh; PPC Mac OS X 10_5_8) AppleWebKit/537.36
```

### iOS (Rejected)
```
Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15
Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15
```

### Android (Rejected)
```
Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36
Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/537.36
```

---

## References

- [Windows Hello Documentation](https://learn.microsoft.com/en-us/windows/security/identity-protection/windows-hello/)
- [macOS Touch ID Documentation](https://support.apple.com/en-us/HT207713)
- [WebAuthn Specification](https://www.w3.org/TR/webauthn-2/)
- [FIDO2 Alliance](https://fidoalliance.org/)
