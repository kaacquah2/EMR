'use client'

import { useAuth } from '@/lib/auth-context'
import { BillingDashboard } from '@/components/features/BillingDashboard'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'

// Receptionist is intentionally excluded: navigation.ts RECEPTIONIST_EXACT_ALLOWED
// does not include /billing, so middleware redirects receptionists to /unauthorized
// before this page renders.  Keep this list in sync with navigation.ts.
const ALLOWED = ['billing_staff', 'hospital_admin', 'super_admin']

export default function BillingPage() {
  const { user } = useAuth()

  if (!user) return null

  if (!ALLOWED.includes(user.role ?? '')) {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to view billing.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: 'Billing & Invoices' }]} />
      <BillingDashboard />
    </div>
  )
}
