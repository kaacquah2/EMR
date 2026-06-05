'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

export default function PharmacyInventoryPage() {
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
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Pharmacy Inventory</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        Pharmacy inventory management is not deployed in the demo runtime.
      </p>
    </div>
  )
}
