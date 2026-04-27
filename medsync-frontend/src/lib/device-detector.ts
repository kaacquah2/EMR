/**
 * Device detection and auto-naming for WebAuthn passkeys.
 * Detects platform (Windows, macOS, Linux, Android, iOS) and device type (desktop, tablet, mobile).
 * Provides user-friendly device names for passkey registration.
 */

export type Platform = 'windows' | 'macos' | 'linux' | 'android' | 'ios' | 'unknown'
export type DeviceType = 'desktop' | 'tablet' | 'mobile'

export interface DeviceInfo {
  type: DeviceType
  platform: Platform
  browser: string
  userAgent: string
  deviceModel?: string // e.g., "iPhone 15 Pro", "SM-G991B"
}

/**
 * Detect the current device platform and type.
 */
export function detectDevice(): DeviceInfo {
  if (typeof navigator === 'undefined') {
    return {
      type: 'desktop',
      platform: 'unknown',
      browser: 'unknown',
      userAgent: 'unknown',
    }
  }

  const ua = navigator.userAgent
  let platform: Platform = 'unknown'
  let type: DeviceType = 'desktop'
  let browser = 'unknown'
  let deviceModel: string | undefined

  // Detect platform
  if (/Windows NT/i.test(ua)) {
    platform = 'windows'
  } else if (/Macintosh|Mac OS X/i.test(ua)) {
    platform = 'macos'
  } else if (/X11|Linux|Ubuntu/i.test(ua)) {
    platform = 'linux'
  } else if (/Android/i.test(ua)) {
    platform = 'android'
  } else if (/iPhone|iPad|iOS|iPod/i.test(ua)) {
    platform = 'ios'
  }

  // Detect device type and model
  if (/iPad/i.test(ua)) {
    type = 'tablet'
    deviceModel = extractIPadModel(ua)
  } else if (/iPhone|iPod/i.test(ua)) {
    type = 'mobile'
    deviceModel = extractiPhoneModel(ua)
  } else if (/Android/i.test(ua)) {
    // Check if tablet or phone
    if (/Tablet|SM-T|Pixel Tablet/i.test(ua)) {
      type = 'tablet'
    } else {
      type = 'mobile'
    }
    deviceModel = extractAndroidModel(ua)
  } else if (/Windows|Macintosh|X11|Linux/i.test(ua)) {
    type = 'desktop'
  }

  // Detect browser
  if (/Chrome|Chromium/i.test(ua) && !/Edge/i.test(ua)) {
    browser = 'Chrome'
  } else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) {
    browser = 'Safari'
  } else if (/Firefox/i.test(ua)) {
    browser = 'Firefox'
  } else if (/Edge|Edg/i.test(ua)) {
    browser = 'Edge'
  } else if (/OPR|Opera/i.test(ua)) {
    browser = 'Opera'
  }

  return {
    type,
    platform,
    browser,
    userAgent: ua,
    deviceModel,
  }
}

/**
 * Extract iPhone model from user agent.
 * e.g., "iPhone 15 Pro", "iPhone 13"
 */
function extractiPhoneModel(ua: string): string | undefined {
  // Modern UA format: "iPhone 15 Pro Max" or older "iPhone 13"
  const match = ua.match(/iPhone.*?(?:Pro Max|Pro|Plus)?/i)
  if (match) return match[0]

  // Fallback: extract from product info
  if (/OS 17/i.test(ua)) return 'iPhone 15'
  if (/OS 16/i.test(ua)) return 'iPhone 14'
  if (/OS 15/i.test(ua)) return 'iPhone 13'
  return 'iPhone'
}

/**
 * Extract iPad model from user agent.
 */
function extractIPadModel(ua: string): string | undefined {
  if (/iPad Pro 12\.9.*?7th/i.test(ua)) return 'iPad Pro 12.9" (7th Gen)'
  if (/iPad Pro 11.*?4th/i.test(ua)) return 'iPad Pro 11" (4th Gen)'
  if (/iPad Air.*?6th/i.test(ua)) return 'iPad Air (6th Gen)'
  if (/iPad mini.*?7th/i.test(ua)) return 'iPad mini (7th Gen)'
  if (/iPad \(10th/i.test(ua)) return 'iPad (10th Gen)'

  // Generic fallback
  if (/iPad Pro/i.test(ua)) return 'iPad Pro'
  if (/iPad Air/i.test(ua)) return 'iPad Air'
  if (/iPad mini/i.test(ua)) return 'iPad mini'
  return 'iPad'
}

/**
 * Extract Android device model from user agent.
 * e.g., "SM-G991B" (Samsung), "Pixel 8"
 */
function extractAndroidModel(ua: string): string | undefined {
  // Common device models
  const models = [
    /Pixel \d+/i,
    /Pixel Pro/i,
    /Galaxy S\d+/i,
    /Galaxy Z Fold/i,
    /Galaxy Z Flip/i,
    /OnePlus \d+/i,
    /Moto G\d+/i,
  ]

  for (const model of models) {
    const match = ua.match(model)
    if (match) return match[0]
  }

  // Try to extract from build info
  const buildMatch = ua.match(/(?:SM-|GT-|LG-)[A-Z0-9]+/i)
  if (buildMatch) return buildMatch[0]

  return undefined
}

/**
 * Get a user-friendly device name from device info.
 * Used for auto-filling passkey device_name on registration.
 */
export function getAutoDeviceName(device: DeviceInfo): string {
  const { type, platform, deviceModel } = device

  // If we have a device model, use it
  if (deviceModel) {
    if (platform === 'ios') return deviceModel
    if (platform === 'android') return deviceModel
  }

  // Fallback to generic names
  const typeNames: Record<DeviceType, string> = {
    desktop: 'Laptop' ,
    tablet: 'Tablet',
    mobile: 'Phone',
  }

  const platformNames: Record<Platform, string> = {
    windows: 'Windows',
    macos: 'Mac',
    linux: 'Linux',
    android: 'Android',
    ios: 'iPhone',
    unknown: 'Device',
  }

  // For desktops, include OS
  if (type === 'desktop') {
    return `${platformNames[platform]} ${typeNames[type]}`
  }

  // For mobile/tablet
  return `${platformNames[platform]} ${typeNames[type]}`
}

/**
 * Get platform emoji for UI display.
 */
export function getPlatformEmoji(platform: Platform): string {
  const emojis: Record<Platform, string> = {
    windows: '🪟',
    macos: '🍎',
    linux: '🐧',
    android: '🤖',
    ios: '📱',
    unknown: '❓',
  }
  return emojis[platform]
}

/**
 * Get platform display name.
 */
export function getPlatformName(platform: Platform): string {
  const names: Record<Platform, string> = {
    windows: 'Windows',
    macos: 'macOS',
    linux: 'Linux',
    android: 'Android',
    ios: 'iOS',
    unknown: 'Unknown',
  }
  return names[platform]
}

/**
 * Get device type icon.
 */
export function getDeviceTypeEmoji(type: DeviceType): string {
  const emojis: Record<DeviceType, string> = {
    desktop: '🖥️',
    tablet: '📱',
    mobile: '📱',
  }
  return emojis[type]
}

/**
 * Format relative time (e.g., "2 hours ago", "3 days ago").
 */
export function formatRelativeTime(date: Date | string | null): string {
  if (!date) return 'Never'

  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)
  const diffWeek = Math.floor(diffDay / 7)
  const diffMonth = Math.floor(diffDay / 30)
  const diffYear = Math.floor(diffDay / 365)

  if (diffSec < 60) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  if (diffWeek < 4) return `${diffWeek}w ago`
  if (diffMonth < 12) return `${diffMonth}mo ago`
  return `${diffYear}y ago`
}
