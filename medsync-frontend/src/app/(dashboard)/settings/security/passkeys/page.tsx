'use client'

import React, { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { usePasskey } from '@/hooks/use-passkey'
import {
  PasskeyList,
  RegisterPasskeyModal,
} from '@/components/features/passkey/PasskeyComponents'

export default function PasskeyManagementPage() {
  const { user } = useAuth()
  const router = useRouter()
  const {
    passkeys,
    isLoading,
    error,
    register,
    list,
    remove,
    rename,
  } = usePasskey()

  const [showRegisterModal, setShowRegisterModal] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [registrationError, setRegistrationError] = useState<string | null>(null)

  const loadPasskeys = useCallback(async () => {
    try {
      await list()
    } catch (err) {
      console.error('Failed to load passkeys:', err)
    }
  }, [list])

  useEffect(() => {
    if (!user) {
      router.push('/login')
      return
    }
    loadPasskeys()
  }, [user, router, loadPasskeys])

  const handleRegisterNew = async (deviceName: string) => {
    setIsRegistering(true)
    setRegistrationError(null)
    try {
      await register(deviceName)
      setShowRegisterModal(false)
      await loadPasskeys()
    } catch (err: unknown) {
      const message = err instanceof Error ? err?.message : 'Failed to register passkey. Please try again.'
      setRegistrationError(message)
    } finally {
      setIsRegistering(false)
    }
  }

  const handleDelete = async (passkeyId: string) => {
    try {
      await remove(passkeyId)
      await loadPasskeys()
    } catch (err) {
      console.error('Failed to delete passkey:', err)
    }
  }

  const handleRename = async (passkeyId: string, newName: string) => {
    try {
      await rename(passkeyId, newName)
      await loadPasskeys()
    } catch (err) {
      console.error('Failed to rename passkey:', err)
    }
  }

  if (!user) {
    return <div>Loading...</div>
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#0F172A] mb-2">Security Keys</h1>
        <p className="text-[#64748B]">
          Manage your passkeys for fast, secure login using biometrics (fingerprint, face ID, Windows Hello).
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-[#FEE2E2] border border-[#FCA5A5] text-[#DC2626]">
          <p className="font-semibold">Error loading passkeys</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      <div className="bg-white rounded-lg border border-[#E2E8F0] p-6 shadow-sm">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-[#0F172A] mb-4">Your Registered Devices</h2>

          <PasskeyList
            passkeys={passkeys}
            isLoading={isLoading}
            onRegisterNew={() => setShowRegisterModal(true)}
            onDelete={handleDelete}
            onRename={handleRename}
          />
        </div>

        {passkeys.length === 0 && !isLoading && (
          <div className="p-4 rounded-lg bg-[#EFF6F5] border border-[#0B8A96]/20">
            <p className="text-sm text-[#0F172A]">
              💡 <strong>Tip:</strong> Register at least one security key to enable fast biometric login.
              You can still use your password and backup codes as fallback.
            </p>
          </div>
        )}

        {passkeys.length > 0 && (
          <div className="mt-6 p-4 rounded-lg bg-[#FEF3C7] border border-[#FCD34D]">
            <p className="text-sm text-[#92400E]">
              ⚠️ <strong>Keep at least one device registered</strong> to ensure you can always log in.
              If you lose access to all devices, contact your administrator.
            </p>
          </div>
        )}
      </div>

      <div className="mt-8 text-sm text-[#64748B]">
        <h3 className="font-semibold text-[#0F172A] mb-3">About Security Keys</h3>
        <ul className="space-y-2 list-disc list-inside">
          <li>Security keys use biometric or hardware authentication (fingerprint, face ID, Windows Hello)</li>
          <li>Your biometric data never leaves your device — MedSync never sees it</li>
          <li>Passkeys are stored in your device&apos;s secure hardware (Trusted Execution Environment)</li>
          <li>You can register different keys on different devices (phone, laptop, tablet)</li>
          <li>Lost access? Use your password and backup codes to log in and re-register new keys</li>
        </ul>
      </div>

      <RegisterPasskeyModal
        isOpen={showRegisterModal}
        isLoading={isRegistering}
        onClose={() => setShowRegisterModal(false)}
        onRegister={handleRegisterNew}
        error={registrationError}
      />
    </div>
  )
}
