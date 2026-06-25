'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { PharmacyDashboard } from '@/components/features/pharmacy/PharmacyDashboard'

export default function PharmacyInventoryPage() {
  const { user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!user) router.push('/login')
  }, [user, router])

  if (!user) return <div className="p-6 text-slate-500">Loading…</div>

  return <PharmacyDashboard />
}
