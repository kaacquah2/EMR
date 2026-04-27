'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogOverlay,
  DialogPortal,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { formatRelativeTime, getPlatformEmoji } from '@/lib/device-detector'
import { useApi } from '@/hooks/use-api'

interface Passkey {
  id: string
  device_name: string
  platform?: string
  created_at: string
  last_used_at?: string
  transports?: string[]
}

interface AdminPasskeyManagementProps {
  userId: string
  userName: string
  userEmail: string
  onResetComplete?: () => void
}

export function AdminPasskeyManagement({
  userId,
  userName,
  userEmail,
  onResetComplete,
}: AdminPasskeyManagementProps) {
  const api = useApi()
  const [isOpen, setIsOpen] = useState(false)
  const [passkeys, setPasskeys] = useState<Passkey[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [isResetting, setIsResetting] = useState(false)

  const loadPasskeys = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.get<{ passkeys: Passkey[] }>(`/admin/users/${userId}/passkeys`)
      setPasskeys(response.passkeys || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load passkeys')
    } finally {
      setIsLoading(false)
    }
  }, [userId, api])

  useEffect(() => {
    if (isOpen) {
      loadPasskeys()
    }
  }, [isOpen, loadPasskeys])

  const handleReset = async () => {
    setIsResetting(true)
    setError(null)
    try {
      await api.post<{ message: string; passkeys_deleted: number }>(`/admin/users/${userId}/passkeys/reset`, {})
      setPasskeys([])
      setShowResetConfirm(false)
      onResetComplete?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset passkeys')
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        variant="outline"
        size="sm"
        className="text-xs"
        data-testid={`admin-passkey-btn-${userId}`}
      >
        Passkeys
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Passkey Management</DialogTitle>
              <DialogClose data-testid={`admin-passkey-close-${userId}`} />
              <p className="text-sm text-gray-600 mt-1">
                {userName} ({userEmail})
              </p>
            </DialogHeader>

          <div className="space-y-4">
            {isLoading && (
              <div className="text-center py-4">
                <div className="text-sm text-gray-500">Loading passkeys...</div>
              </div>
            )}

            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {!isLoading && passkeys.length === 0 && (
              <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700">
                No passkeys registered for this user.
              </div>
            )}

            {!isLoading && passkeys.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-900">
                  Registered Passkeys ({passkeys.length})
                </p>
                <div className="space-y-2">
                  {passkeys.map((pk) => (
                    <div
                      key={pk.id}
                      className="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900 flex items-center gap-2">
                            {pk.platform && getPlatformEmoji(pk.platform as 'windows' | 'macos' | 'linux' | 'android' | 'ios' | 'unknown')}
                            {pk.device_name}
                          </div>
                          <div className="text-xs text-gray-600 mt-1">
                            Registered:{' '}
                            {formatRelativeTime(new Date(pk.created_at))}
                          </div>
                          {pk.last_used_at && (
                            <div className="text-xs text-gray-600">
                              Last used:{' '}
                              {formatRelativeTime(new Date(pk.last_used_at))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="border-t pt-4 space-y-3">
              <p className="text-sm text-gray-700">
                <strong>Reset Passkeys:</strong> Remove all registered passkeys
                for this user. They will be prompted to re-register on next login
                or can register a new device in settings.
              </p>
              <Button
                onClick={() => setShowResetConfirm(true)}
                variant="danger"
                fullWidth
                disabled={isResetting}
                data-testid={`admin-passkey-reset-btn-${userId}`}
              >
                {isResetting ? 'Resetting...' : 'Reset All Passkeys'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
      </Dialog>

      <ConfirmDialog
        open={showResetConfirm}
        onOpenChange={setShowResetConfirm}
        title="Reset Passkeys?"
        message={`This will remove all ${passkeys.length} passkey(s) for ${userEmail}. They will need to re-register passkeys on their devices.`}
        confirmLabel="Reset Passkeys"
        onConfirm={handleReset}
        variant="danger"
        loading={isResetting}
      />
    </>
  )
}
