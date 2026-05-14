/**
 * Passkey management UI components for multi-device support.
 */
'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import {
  detectDevice,
  getAutoDeviceName,
  getPlatformEmoji,
  getPlatformName,
  formatRelativeTime,
} from '@/lib/device-detector'
import type { Passkey } from '@/hooks/use-passkey'

interface PasskeyListProps {
  passkeys: Passkey[]
  isLoading?: boolean
  onRegisterNew?: () => void
  onDelete?: (passkeyId: string) => void
  onRename?: (passkeyId: string, newName: string) => Promise<void>
}

/**
 * Display list of registered passkeys with device info.
 */
export function PasskeyList({
  passkeys,
  isLoading = false,
  onRegisterNew,
  onDelete,
  onRename,
}: PasskeyListProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-16 bg-gray-200 rounded animate-pulse" />
        <div className="h-16 bg-gray-200 rounded animate-pulse" />
      </div>
    )
  }

  if (passkeys.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-8 text-center">
        <p className="text-sm text-slate-500 dark:text-slate-500">
          No passkeys registered yet. Register your first passkey to enable quick biometric login.
        </p>
        <Button
          onClick={onRegisterNew}
          className="mt-4 bg-[#0B8A96] hover:bg-[#067A85]"
        >
          Register Passkey on This Device
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {passkeys.map((passkey) => (
        <PasskeyItem
          key={passkey.id}
          passkey={passkey}
          onDelete={onDelete}
          onRename={onRename}
        />
      ))}
      {onRegisterNew && (
        <Button
          onClick={onRegisterNew}
          variant="outline"
          fullWidth
          className="mt-4 border-slate-300 dark:border-slate-700"
        >
          + Register New Passkey
        </Button>
      )}
    </div>
  )
}

/**
 * Single passkey item with actions.
 */
function PasskeyItem({
  passkey,
  onDelete,
  onRename,
}: {
  passkey: Passkey
  onDelete?: (id: string) => void
  onRename?: (id: string, name: string) => Promise<void>
}) {
  const [showRenameInput, setShowRenameInput] = useState(false)
  const [newName, setNewName] = useState(passkey.device_name)
  const [isRenaming, setIsRenaming] = useState(false)

  const handleRenameSubmit = async () => {
    if (newName.trim() && newName !== passkey.device_name) {
      setIsRenaming(true)
      try {
        await onRename?.(passkey.id, newName)
        setShowRenameInput(false)
      } finally {
        setIsRenaming(false)
      }
    }
  }

  const platformEmoji = getPlatformEmoji((passkey.platform as 'windows' | 'macos' | 'linux' | 'android' | 'ios' | 'unknown' | undefined) || 'unknown')
  const platformName = getPlatformName((passkey.platform as 'windows' | 'macos' | 'linux' | 'android' | 'ios' | 'unknown' | undefined) || 'unknown')
  const lastUsedText = passkey.last_used_at ? formatRelativeTime(passkey.last_used_at) : 'Never'

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          {showRenameInput ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
                className="flex-1 rounded border border-slate-300 dark:border-slate-700 px-2 py-1 text-sm"
                data-testid="passkey-rename-input"
                disabled={isRenaming}
              />
              <button
                onClick={handleRenameSubmit}
                className="px-2 py-1 text-sm bg-[#0B8A96] text-white rounded hover:bg-[#067A85] disabled:opacity-50"
                disabled={isRenaming}
              >
                {isRenaming ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={() => {
                  setShowRenameInput(false)
                  setNewName(passkey.device_name)
                }}
                className="px-2 py-1 text-sm border border-slate-300 dark:border-slate-700 rounded hover:bg-slate-50 dark:bg-slate-900"
                disabled={isRenaming}
              >
                Cancel
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{platformEmoji}</span>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100">{passkey.device_name}</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-500">{platformName}</p>
                </div>
              </div>
              <div className="text-xs text-[#94A3B8] space-y-1">
                <p>Registered {formatRelativeTime(passkey.created_at)}</p>
                {passkey.last_used_at && (
                  <p>Last used {lastUsedText}</p>
                )}
              </div>
            </>
          )}
        </div>

        {!showRenameInput && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowRenameInput(true)}
              className="p-2 text-slate-500 dark:text-slate-500 hover:text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:bg-slate-900 rounded"
              data-testid={`passkey-rename-${passkey.id}`}
              title="Rename device"
            >
              ✏️
            </button>
            {onDelete && (
              <button
                onClick={() => {
                  if (confirm(`Remove passkey "${passkey.device_name}"? You won't be able to use this device to log in.`)) {
                    onDelete(passkey.id)
                  }
                }}
                className="p-2 text-[#DC2626] hover:text-[#7F1D1D] hover:bg-[#FEE2E2] rounded"
                data-testid={`passkey-delete-${passkey.id}`}
                title="Delete passkey"
              >
                🗑️
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface RegisterPasskeyModalProps {
  isOpen: boolean
  isLoading?: boolean
  onClose: () => void
  onRegister: (deviceName: string) => Promise<void>
  error?: string | null
}

/**
 * Modal for registering a new passkey with device detection.
 */
export function RegisterPasskeyModal({
  isOpen,
  isLoading = false,
  onClose,
  onRegister,
  error,
}: RegisterPasskeyModalProps) {
  const [deviceName, setDeviceName] = useState('')
  const [useAutoName, setUseAutoName] = useState(true)

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDeviceName('')
      setUseAutoName(true)
    }
  }, [isOpen])

  // Auto-populate device name when modal opens with useAutoName enabled
  useEffect(() => {
    if (isOpen && useAutoName && deviceName === '') {
      const device = detectDevice()
      const autoName = getAutoDeviceName(device)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDeviceName(autoName)
    }
  }, [isOpen, useAutoName, deviceName])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await onRegister(deviceName)
      onClose()
      setDeviceName('')
      setUseAutoName(true)
    } catch {
      // Error handled by parent
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">Register Passkey</h2>

        {error && (
          <div className="mb-4 p-3 rounded bg-[#FEE2E2] text-[#DC2626] text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-900 dark:text-slate-100 mb-2">
              Device Name
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => {
                setDeviceName(e.target.value)
                setUseAutoName(false)
              }}
              placeholder="e.g., Ward Tablet, Personal iPhone"
              className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2"
              data-testid="passkey-device-name"
              required
              disabled={isLoading}
            />
            <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">
              Choose a name that helps you remember this device (e.g., &quot;Ward Laptop&quot;, &quot;Personal Phone&quot;)
            </p>
          </div>

          <div className="p-3 rounded bg-[#EFF6F5] border border-[#0B8A96]/20">
            <p className="text-sm text-slate-900 dark:text-slate-100">
              <strong>Next:</strong> Your device will prompt for biometric confirmation (fingerprint, face ID, or Windows Hello).
            </p>
          </div>

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded hover:bg-slate-50 dark:bg-slate-900"
              disabled={isLoading}
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={isLoading || !deviceName.trim()}
              className="bg-[#0B8A96] hover:bg-[#067A85]"
            >
              {isLoading ? 'Registering...' : '👆 Register with Biometric'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
