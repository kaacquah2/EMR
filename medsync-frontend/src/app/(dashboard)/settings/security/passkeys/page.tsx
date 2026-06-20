'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { useApi } from '@/hooks/use-api'
import { useToast } from '@/lib/toast-context'
import {
  isPlatformAuthenticatorAvailable,
  registerPasskey,
  listPasskeys,
  deletePasskey,
  renamePasskey,
} from '@/lib/passkey'
import { detectDevice, getAutoDeviceName } from '@/lib/device-detector'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'
import {
  KeyRound,
  ShieldCheck,
  ShieldX,
  Trash2,
  Pencil,
  Plus,
  Loader2,
  MonitorSmartphone,
  CheckCircle2,
} from 'lucide-react'

interface Passkey {
  id: string
  device_name: string
  platform?: string
  created_at: string
  last_used_at?: string
  transports?: string[]
}

export default function PasskeysPage() {
  const { user } = useAuth()
  const api = useApi()
  const toast = useToast()

  const [supported, setSupported] = useState<boolean | null>(null)
  const [passkeys, setPasskeys] = useState<Passkey[]>([])
  const [loading, setLoading] = useState(true)
  const [registering, setRegistering] = useState(false)
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Check platform support
  useEffect(() => {
    void isPlatformAuthenticatorAvailable().then(setSupported)
  }, [])

  // Auto-fill device name on mount
  useEffect(() => {
    setNewName(getAutoDeviceName(detectDevice()))
  }, [])

  const fetchPasskeys = useCallback(async () => {
    setLoading(true)
    try {
      const list = await listPasskeys(api)
      setPasskeys(Array.isArray(list) ? list : [])
    } catch {
      toast.error('Failed to load passkeys')
    } finally {
      setLoading(false)
    }
  }, [api, toast])

  useEffect(() => {
    void fetchPasskeys()
  }, [fetchPasskeys])

  const handleRegister = async () => {
    if (!newName.trim()) {
      toast.error('Please enter a name for this passkey')
      return
    }
    setRegistering(true)
    try {
      await registerPasskey(api, newName.trim())
      toast.success('Passkey registered successfully')
      setNewName(getAutoDeviceName(detectDevice()))
      void fetchPasskeys()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to register passkey')
    } finally {
      setRegistering(false)
    }
  }

  const handleRename = async (id: string) => {
    if (!editName.trim()) return
    try {
      await renamePasskey(api, id, editName.trim())
      toast.success('Passkey renamed')
      setEditingId(null)
      void fetchPasskeys()
    } catch {
      toast.error('Failed to rename passkey')
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await deletePasskey(api, id)
      toast.success('Passkey removed')
      void fetchPasskeys()
    } catch {
      toast.error('Failed to remove passkey')
    } finally {
      setDeletingId(null)
    }
  }

  if (!user) return null

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-6 px-4">
      <Breadcrumbs items={[{ label: 'Settings' }, { label: 'Security Keys' }]} />

      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <KeyRound className="h-6 w-6 text-[#6366F1]" />
          Passkeys & Security Keys
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Register biometric credentials (Windows Hello, macOS Touch ID) to sign in without typing your password.
        </p>
      </div>

      {/* Platform Support Banner */}
      <Card>
        <CardContent className="pt-4 pb-4">
          {supported === null ? (
            <div className="flex items-center gap-2 text-slate-500 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Checking device compatibility…
            </div>
          ) : supported ? (
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 text-sm">
              <ShieldCheck className="h-5 w-5 shrink-0" />
              <span>
                <strong>Your device supports passkeys.</strong> You can register Windows Hello or macOS Touch ID/Face ID.
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400 text-sm">
              <ShieldX className="h-5 w-5 shrink-0 mt-0.5" />
              <span>
                <strong>Passkeys are not available on this device.</strong> Passkey authentication requires a Windows laptop with Windows Hello, or a MacBook with Touch ID/Face ID. Mobile devices are not supported.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Register new passkey */}
      {supported && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Register a new passkey
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Device name
              </label>
              <Input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Work MacBook Pro"
                className="bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100"
                disabled={registering}
              />
              <p className="mt-1 text-xs text-slate-400">
                Give this passkey a name so you can identify it later.
              </p>
            </div>
            <Button
              onClick={() => void handleRegister()}
              disabled={registering || !newName.trim()}
              className="bg-[#6366F1] hover:bg-[#4F46E5] text-white flex items-center gap-1.5"
            >
              {registering ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Waiting for biometric prompt…
                </>
              ) : (
                <>
                  <MonitorSmartphone className="h-4 w-4" />
                  Register this device
                </>
              )}
            </Button>
            {registering && (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Your device will ask you to authenticate with Windows Hello or Touch ID. Follow the prompt to complete registration.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Registered passkeys list */}
      <Card>
        <CardHeader>
          <CardTitle>Registered passkeys</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-slate-500 text-sm py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading passkeys…
            </div>
          ) : passkeys.length === 0 ? (
            <div className="text-center py-6 text-slate-400">
              <KeyRound className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No passkeys registered yet.</p>
              {supported && (
                <p className="text-xs mt-1">Register your first passkey above to enable passwordless sign-in.</p>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {passkeys.map((pk) => (
                <li key={pk.id} className="py-4">
                  {editingId === pk.id ? (
                    <div className="flex items-center gap-2">
                      <Input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 h-8 text-sm"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') void handleRename(pk.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                      />
                      <Button size="sm" onClick={() => void handleRename(pk.id)} className="h-8">
                        Save
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditingId(null)} className="h-8">
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-[#6366F1]/10">
                          <KeyRound className="h-4 w-4 text-[#6366F1]" />
                        </div>
                        <div>
                          <p className="font-medium text-sm text-slate-900 dark:text-slate-100">
                            {pk.device_name}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                            <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                            <span>Registered {new Date(pk.created_at).toLocaleDateString('en-GB')}</span>
                            {pk.last_used_at && (
                              <>
                                <span>·</span>
                                <span>Last used {new Date(pk.last_used_at).toLocaleDateString('en-GB')}</span>
                              </>
                            )}
                            {pk.platform && (
                              <>
                                <span>·</span>
                                <span className="capitalize">{pk.platform}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => {
                            setEditingId(pk.id)
                            setEditName(pk.device_name)
                          }}
                          className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                          title="Rename"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => void handleDelete(pk.id)}
                          disabled={deletingId === pk.id}
                          className="p-1.5 rounded hover:bg-rose-50 dark:hover:bg-rose-900/20 text-slate-400 hover:text-rose-600"
                          title="Remove passkey"
                        >
                          {deletingId === pk.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-slate-400 text-center">
        Passkeys are tied to this specific device. If you lose access to a device, remove its passkey above.
        You can always sign in with your email and password + MFA code instead.
      </p>
    </div>
  )
}
