/**
 * WebAuthn/Passkey utilities for MedSync.
 * 
 * Handles passkey registration and authentication ceremonies
 * with proper error handling and type safety.
 */

interface ApiClient {
  post<T>(path: string, data: Record<string, unknown>): Promise<T>
  get<T>(path: string): Promise<T>
  delete(path: string): Promise<void>
}

/**
 * Check if device platform is supported (Windows or macOS only).
 * Mobile devices are not supported in this deployment.
 */
function isSupportedPlatform(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = (navigator.userAgent || '').toLowerCase()
  return /windows|macintosh|mac os x/.test(ua)
}

/**
 * Check if this browser/device supports WebAuthn passkeys.
 * MedSync is desktop-only: Windows Hello and macOS biometrics only.
 */
export function isPasskeySupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    isSupportedPlatform() &&
    window.PublicKeyCredential !== undefined &&
    typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === 'function'
  )
}

/**
 * Check if platform authenticator (Windows Hello or macOS Touch ID/Face ID) is available.
 * Only returns true for supported desktop platforms.
 * Returns diagnostic info for debugging when unavailable.
 */
export async function isPlatformAuthenticatorAvailable(): Promise<boolean> {
  if (!isPasskeySupported()) {
    console.debug('[Passkey] Platform not supported - not Windows or macOS');
    return false;
  }
  
  // Check if PublicKeyCredential API exists
  if (typeof PublicKeyCredential === 'undefined') {
    console.warn('[Passkey] WebAuthn API not available - browser may not support it');
    return false;
  }
  
  // Check if the method exists
  if (typeof PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable !== 'function') {
    console.warn('[Passkey] Platform authenticator check not available');
    return false;
  }
  
  try {
    const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    console.debug('[Passkey] Platform authenticator available:', available);
    return available;
  } catch (err) {
    console.warn('[Passkey] Error checking platform authenticator availability:', err);
    return false;
  }
}

/**
 * Get user-friendly platform name for error messages.
 */

/**
 * Convert ArrayBuffer to base64url string for transmission.
 */
export function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

/**
 * Convert base64url string back to ArrayBuffer.
 */
export function base64urlToBuffer(base64url: string): ArrayBuffer {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

interface AttestationResponse {
  clientDataJSON: ArrayBuffer
  attestationObject: ArrayBuffer
  getTransports?(): string[]
}

interface AssertionResponse {
  authenticatorData: ArrayBuffer
  clientDataJSON: ArrayBuffer
  signature: ArrayBuffer
  userHandle: ArrayBuffer | null
}

/**
 * Convert WebAuthn credential to JSON for transmission.
 */
export function credentialToJSON(credential: PublicKeyCredential | AuthenticatorAssertionResponse): Record<string, unknown> {
  const cred = credential as unknown as { rawId: ArrayBuffer; type: string; response: AttestationResponse | AssertionResponse }
  const response = cred.response as unknown as Partial<AttestationResponse & AssertionResponse>
  
  if (response.clientDataJSON && response.attestationObject) {
    // PublicKeyCredential (registration)
    return {
      id: bufferToBase64url(cred.rawId),
      rawId: bufferToBase64url(cred.rawId),
      response: {
        attestationObject: bufferToBase64url(response.attestationObject),
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
      },
      type: cred.type,
      transports: (response.getTransports as unknown as (() => string[]) | undefined)?.() || [],
    }
  } else {
    // AuthenticatorAssertionResponse (authentication)
    return {
      id: bufferToBase64url(cred.rawId),
      rawId: bufferToBase64url(cred.rawId),
      response: {
        authenticatorData: bufferToBase64url(response.authenticatorData!),
        clientDataJSON: bufferToBase64url(response.clientDataJSON!),
        signature: bufferToBase64url(response.signature!),
        userHandle: response.userHandle
          ? bufferToBase64url(response.userHandle)
          : null,
      },
      type: cred.type,
    }
  }
}

/**
 * Convert WebAuthn options from JSON to format expected by browser API.
 */
export function optionsToWebAuthn(options: Record<string, unknown>): PublicKeyCredentialCreationOptions | PublicKeyCredentialRequestOptions {
  const opts = options as Record<string, unknown> & { 
    challenge?: string | ArrayBuffer
    user?: { id: string | ArrayBuffer }
    excludeCredentials?: Array<{ id: string | ArrayBuffer; transports?: string[] }>
    allowCredentials?: Array<{ id: string | ArrayBuffer; transports?: string[] }>
  }
  
  // Convert challenge back to ArrayBuffer
  if (typeof opts.challenge === 'string') {
    opts.challenge = base64urlToBuffer(opts.challenge)
  }

  // For registration options
  if (opts.user) {
    if (typeof opts.user.id === 'string') {
      opts.user.id = base64urlToBuffer(opts.user.id)
    }
    if (opts.excludeCredentials) {
      opts.excludeCredentials = opts.excludeCredentials.map((cred) => ({
        type: 'public-key' as const,
        id: typeof cred.id === 'string' ? base64urlToBuffer(cred.id) : cred.id,
        transports: cred.transports,
      }))
    }
  return opts as unknown as PublicKeyCredentialCreationOptions
  }

  // For authentication options
  if (opts.allowCredentials) {
    opts.allowCredentials = opts.allowCredentials.map((cred) => ({
      type: 'public-key' as const,
      id: typeof cred.id === 'string' ? base64urlToBuffer(cred.id) : cred.id,
      transports: cred.transports,
    }))
  }

  return opts as PublicKeyCredentialRequestOptions
}

/**
 * Register a new passkey.
 * 
 * MedSync is desktop-only and supports:
 * - Windows laptops with Windows Hello
 * - macBooks with Touch ID/Face ID
 */
export async function registerPasskey(apiClient: ApiClient, deviceName: string): Promise<void> {
  if (!isPasskeySupported()) {
    const ua = (navigator.userAgent || '').toLowerCase()
    if (/iphone|ipad|ipod|android/.test(ua)) {
      throw new Error(
        'MedSync does not support mobile devices. Please use a Windows laptop or MacBook to register a passkey.'
      )
    }
    throw new Error(
      'Passkey registration requires Windows Hello or macOS Touch ID/Face ID. Please ensure your device supports biometric authentication.'
    )
  }

  try {
    // Step 1: Get registration options from server
    const optionsResponse = await apiClient.post<Record<string, unknown>>('/auth/passkey/register/begin', {})
    const options = optionsToWebAuthn(optionsResponse)

    // Step 2: Create credential (browser will show biometric prompt)
    const credential = await navigator.credentials.create({
      publicKey: options as unknown as PublicKeyCredentialCreationOptions,
    })

    if (!credential) {
      throw new Error('Passkey registration cancelled or failed')
    }

    // Step 3: Send credential to server
    const credentialData = credentialToJSON(credential as PublicKeyCredential)
    await apiClient.post('/auth/passkey/register/complete', {
      ...credentialData,
      device_name: deviceName,
    })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to register passkey'
    throw new Error(message)
  }
}

/**
 * Authenticate with a passkey.
 * 
 * MedSync is desktop-only and supports:
 * - Windows laptops with Windows Hello
 * - macBooks with Touch ID/Face ID
 */
export async function authenticateWithPasskey(
  apiClient: ApiClient,
  email: string
): Promise<{
  access_token: string
  refresh_token: string
  user_profile: Record<string, unknown>
  role: string
}> {
  if (!isPasskeySupported()) {
    const ua = (navigator.userAgent || '').toLowerCase()
    if (/iphone|ipad|ipod|android/.test(ua)) {
      throw new Error(
        'MedSync does not support mobile devices. Please use a Windows laptop or MacBook to sign in.'
      )
    }
    throw new Error(
      'Passkey authentication requires Windows Hello or macOS Touch ID/Face ID. Please ensure your device supports biometric authentication.'
    )
  }

  try {
    // Step 1: Get authentication options from server
    const optionsResponse = await apiClient.post<Record<string, unknown>>('/auth/passkey/auth/begin', { email })
    const options = optionsToWebAuthn(optionsResponse)

    // Step 2: Get credential assertion (browser will show biometric prompt)
    const assertion = await navigator.credentials.get({
      publicKey: options as unknown as PublicKeyCredentialRequestOptions,
    })

    if (!assertion) {
      throw new Error('Passkey authentication cancelled by user')
    }

    // Step 3: Send assertion to server
    const assertionData = credentialToJSON(assertion as unknown as PublicKeyCredential)
    const response = await apiClient.post<{ access_token: string; refresh_token: string; user_profile: Record<string, unknown>; role: string }>('/auth/passkey/auth/complete', assertionData)

    return response
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to authenticate with passkey'
    throw new Error(message)
  }
}

interface Passkey {
  id: string
  device_name: string
  platform?: string
  created_at: string
  last_used_at?: string
  transports?: string[]
}

/**
 * Get list of passkeys registered for current user.
 */
export async function listPasskeys(apiClient: ApiClient): Promise<Passkey[]> {
  const response = await apiClient.get<Passkey[]>('/auth/passkeys')
  return response
}

/**
 * Delete a passkey by ID.
 */
export async function deletePasskey(apiClient: ApiClient, passkeyId: string): Promise<void> {
  await apiClient.delete(`/auth/passkeys/${passkeyId}`)
}

/**
 * Rename a passkey by ID.
 */
export async function renamePasskey(apiClient: ApiClient, passkeyId: string, newName: string): Promise<void> {
  await apiClient.post(`/auth/passkeys/${passkeyId}/rename`, {
    new_name: newName,
  })
}
