/**
 * Device policy enforcement for MedSync.
 * 
 * MedSync is a desktop-only clinical system designed for:
 * - Windows laptops with Windows Hello biometric
 * - macBooks with Touch ID/Face ID biometric
 * 
 * Mobile devices are not supported.
 */

export interface DevicePolicy {
  isSupported: boolean
  platform: 'windows' | 'macos' | 'unsupported'
  platformName: string
  biometricSupport: string
  warning: string | null
}

/**
 * Detect and validate device platform.
 * Returns warnings for unsupported platforms but doesn't block.
 */
export function validateDevicePolicy(): DevicePolicy {
  if (typeof navigator === 'undefined') {
    return {
      isSupported: false,
      platform: 'unsupported',
      platformName: 'Unknown',
      biometricSupport: 'Unknown',
      warning: 'Could not detect device platform',
    }
  }

  const ua = (navigator.userAgent || '').toLowerCase()

  // Detect platform
  let platform: 'windows' | 'macos' | 'unsupported' = 'unsupported'
  let platformName = 'Unsupported Device'
  let biometricSupport = 'Not available'
  let warning: string | null = null

  if (/windows|win32|win64/.test(ua)) {
    platform = 'windows'
    platformName = 'Windows'
    biometricSupport = 'Windows Hello (fingerprint, face, PIN)'
  } else if (/macintosh|mac os x|macos/.test(ua)) {
    platform = 'macos'
    platformName = 'macOS'
    biometricSupport = 'Touch ID or Face ID'
  } else if (/iphone|ipad|ipod|ios/.test(ua)) {
    platform = 'unsupported'
    platformName = 'iOS'
    biometricSupport = 'Not supported'
    warning = '⚠️ MedSync does not support iOS. Please use a Windows laptop or MacBook to access MedSync.'
  } else if (/android/.test(ua)) {
    platform = 'unsupported'
    platformName = 'Android'
    biometricSupport = 'Not supported'
    warning = '⚠️ MedSync does not support Android. Please use a Windows laptop or MacBook to access MedSync.'
  } else if (/linux|x11|ubuntu/.test(ua)) {
    platform = 'unsupported'
    platformName = 'Linux'
    biometricSupport = 'Not supported'
    warning = '⚠️ MedSync requires Windows or macOS. Linux is not supported.'
  }

  return {
    isSupported: platform !== 'unsupported',
    platform,
    platformName,
    biometricSupport,
    warning,
  }
}

/**
 * Check if HTTPS is enforced for production.
 * Clinical systems must use HTTPS for security and compliance.
 */
export function validateHttpsPolicy(): boolean {
  if (typeof window === 'undefined') return true

  const isProduction = process.env.NODE_ENV === 'production'
  const isHttps = window.location.protocol === 'https:'
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

  // Allow HTTP only for localhost development
  if (!isProduction || isLocalhost) return true

  // Production must use HTTPS
  if (!isHttps) {
    console.error(
      '🔒 SECURITY ERROR: MedSync requires HTTPS in production. ' +
      'Clinical data must be encrypted in transit. Current URL: ' + window.location.href
    )
    return false
  }

  return true
}

/**
 * Get device policy recommendation message for UI display.
 */
export function getDevicePolicyMessage(policy: DevicePolicy): string | null {
  if (policy.isSupported) {
    return null // No message needed for supported devices
  }

  return (
    policy.warning ||
    `MedSync is designed for Windows laptops and macBooks. ` +
    `Your device (${policy.platformName}) is not supported. ` +
    `Please use a Windows laptop or MacBook with biometric authentication enabled.`
  )
}

/**
 * Store device policy check result in session storage.
 * Used to avoid repeated checks on every page load.
 */
export function cacheDevicePolicyCheck(policy: DevicePolicy): void {
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(
        'medsync_device_policy',
        JSON.stringify({
          ...policy,
          checkedAt: new Date().toISOString(),
        })
      )
    }
  } catch {
    // Silently fail if sessionStorage is not available
  }
}

/**
 * Get cached device policy check, if still valid (5 minutes).
 */
export function getCachedDevicePolicy(): DevicePolicy | null {
  try {
    if (typeof sessionStorage === 'undefined') return null

    const cached = sessionStorage.getItem('medsync_device_policy')
    if (!cached) return null

    const parsed = JSON.parse(cached)
    const checkedAt = new Date(parsed.checkedAt).getTime()
    const now = new Date().getTime()
    const fiveMinutesMs = 5 * 60 * 1000

    // Cache is valid for 5 minutes
    if (now - checkedAt > fiveMinutesMs) {
      sessionStorage.removeItem('medsync_device_policy')
      return null
    }

    return parsed
  } catch {
    return null
  }
}
