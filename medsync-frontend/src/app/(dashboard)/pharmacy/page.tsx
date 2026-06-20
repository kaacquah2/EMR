'use client'

import { useAuth } from '@/lib/auth-context'
import { PharmacyDashboard } from '@/components/features/pharmacy/PharmacyDashboard'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'

const ALLOWED = ['pharmacy_technician', 'hospital_admin', 'super_admin']

export default function PharmacyPage() {
  const { user } = useAuth()

  if (!user) return null

  if (!ALLOWED.includes(user.role ?? '')) {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to view the pharmacy module.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: 'Pharmacy' }]} />
      <PharmacyDashboard />
    </div>
  )
}
