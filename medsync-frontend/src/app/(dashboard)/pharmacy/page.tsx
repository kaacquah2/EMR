'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

export default function PharmacyPage() {
  const { user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!user) {
      router.push('/login')
    }
  }, [user, router])

  if (!user) {
    return <div>Loading...</div>
  }

  return (
    <div className="mx-auto max-w-2xl py-10 px-4">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Pharmacy</h1>
      <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
        Pharmacy inventory and dispensation management is available to pharmacy technicians
        via the inventory sub-section. Drug dispensation is also accessible directly from
        the nurse worklist (Dispense Medications).
      </p>
      <div className="mt-6 space-y-2 text-sm">
        <a href="/pharmacy/inventory" className="block rounded-lg border border-slate-200 dark:border-slate-800 px-4 py-3 font-medium text-[#0B8A96] hover:bg-slate-50 dark:hover:bg-slate-900">
          → Pharmacy Inventory
        </a>
        <a href="/worklist/handover" className="block rounded-lg border border-slate-200 dark:border-slate-800 px-4 py-3 font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900">
          → Nurse Worklist &amp; Handover
        </a>
      </div>
    </div>
  )
}
