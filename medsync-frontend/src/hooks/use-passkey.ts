/**
 * Custom hook for WebAuthn/Passkey operations.
 * Provides passkey registration, authentication, and management.
 */
import { useState, useCallback, useEffect } from 'react'
import { useApi } from './use-api'
import {
  isPasskeySupported,
  isPlatformAuthenticatorAvailable,
  registerPasskey,
  authenticateWithPasskey,
  listPasskeys,
  deletePasskey,
  renamePasskey,
} from '@/lib/passkey'

export interface Passkey {
  id: string
  device_name: string
  platform?: string
  created_at: string
  last_used_at: string | null
  transports: string[]
}

export interface UsePasskeyReturn {
  isSupported: boolean
  isPlatformAvailable: boolean
  passkeys: Passkey[]
  isLoading: boolean
  error: string | null
  register: (deviceName: string) => Promise<void>
  authenticate: (email: string) => Promise<unknown>
  list: () => Promise<void>
  remove: (passkeyId: string) => Promise<void>
  rename: (passkeyId: string, newName: string) => Promise<void>
  clearError: () => void
}

export function usePasskey(): UsePasskeyReturn {
  const apiClient = useApi()
  const [isSupported] = useState(isPasskeySupported())
  const [isPlatformAvailable, setIsPlatformAvailable] = useState(false)
  const [passkeys, setPasskeys] = useState<Passkey[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Check platform authenticator availability on mount
  useEffect(() => {
    if (isSupported) {
      isPlatformAuthenticatorAvailable().then(setIsPlatformAvailable)
    }
  }, [isSupported])

  const clearError = useCallback(() => setError(null), [])

  // Define list first since it's used by other callbacks
  const list = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const keys = await listPasskeys(apiClient)
      // Normalize undefined fields to match Passkey interface
      setPasskeys(keys.map(k => ({ 
        ...k, 
        last_used_at: k.last_used_at || null,
        transports: k.transports || []
      })))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to list passkeys'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [apiClient])

  const register = useCallback(
    async (deviceName: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await registerPasskey(apiClient, deviceName)
        // Refresh passkey list
        await list()
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to register passkey'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [apiClient, list]
  )

  const authenticate = useCallback(
    async (email: string) => {
      setIsLoading(true)
      setError(null)
      try {
        const result = await authenticateWithPasskey(apiClient, email)
        return result
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to authenticate with passkey'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [apiClient]
  )

  const remove = useCallback(
    async (passkeyId: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await deletePasskey(apiClient, passkeyId)
        // Refresh passkey list
        await list()
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to delete passkey'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [apiClient, list]
  )

  const rename = useCallback(
    async (passkeyId: string, newName: string) => {
      setIsLoading(true)
      setError(null)
      try {
        await renamePasskey(apiClient, passkeyId, newName)
        // Refresh passkey list
        await list()
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to rename passkey'
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [apiClient, list]
  )

  return {
    isSupported,
    isPlatformAvailable,
    passkeys,
    isLoading,
    error,
    register,
    authenticate,
    list,
    remove,
    rename,
    clearError,
  }
}
