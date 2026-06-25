'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { usePasskey } from '@/hooks/use-passkey'
import {
  PasskeyList,
  RegisterPasskeyModal,
} from '@/components/features/passkey/PasskeyComponents'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function PasskeysPage() {
  const { user } = useAuth()
  const router = useRouter()
  const {
    passkeys,
    isSupported,
    isPlatformAvailable,
    isLoading,
    error,
    register,
    remove,
    rename,
    list,
    clearError,
  } = usePasskey()
  const [showRegisterModal, setShowRegisterModal] = useState(false)

  useEffect(() => {
    if (!user) router.push('/login')
  }, [user, router])

  useEffect(() => {
    if (user) list()
  // list is stable (useCallback), run once on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  if (!user) return <div className="p-6 text-slate-500">Loading…</div>

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-8 px-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Security Keys</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Passkeys let you sign in with biometrics — fingerprint, face ID, or Windows Hello — faster
            and more secure than passwords.
          </p>
        </div>
        {isSupported && (
          <Button
            className="shrink-0 bg-[#0B8A96] hover:bg-[#067A85]"
            onClick={() => setShowRegisterModal(true)}
          >
            + Add Passkey
          </Button>
        )}
      </div>

      {!isSupported && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Your browser does not support passkeys. Use a modern browser such as Chrome 108+, Safari 16+,
          or Edge 108+.
        </div>
      )}

      {isSupported && !isPlatformAvailable && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          No platform authenticator detected. You can still register a security key (e.g. YubiKey) but
          biometric login may not be available on this device.
        </div>
      )}

      {error && (
        <div className="flex items-start justify-between rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <span>{error}</span>
          <button
            onClick={clearError}
            className="ml-4 shrink-0 font-medium underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Registered Passkeys</CardTitle>
          <CardDescription>
            Devices you can use to sign in without a password.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PasskeyList
            passkeys={passkeys}
            isLoading={isLoading}
            onRegisterNew={isSupported ? () => setShowRegisterModal(true) : undefined}
            onDelete={remove}
            onRename={rename}
          />
        </CardContent>
      </Card>

      <RegisterPasskeyModal
        isOpen={showRegisterModal}
        isLoading={isLoading}
        onClose={() => setShowRegisterModal(false)}
        onRegister={register}
        error={error}
      />
    </div>
  )
}
