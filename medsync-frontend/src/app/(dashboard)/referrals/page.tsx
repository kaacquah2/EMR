"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useReferrals } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ReferralStatus } from "@/lib/types";
import { EmptyState } from "@/components/ui/empty-state";
import { ArrowRightLeft } from "lucide-react";

const statusVariant: Record<ReferralStatus, "active" | "pending" | "default" | "critical"> = {
  PENDING: "pending",
  ACCEPTED: "active",
  REJECTED: "critical",
  COMPLETED: "default",
};

const REFERRAL_ROLES = ["doctor", "hospital_admin", "super_admin"];

export default function ReferralsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { incoming, loading, error, fetchIncoming, updateStatus } = useReferrals();
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const canAccess = user?.role && REFERRAL_ROLES.includes(user.role);

  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);
  useEffect(() => {
    if (canAccess) fetchIncoming();
  }, [fetchIncoming, canAccess]);

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">Redirecting...</div>;

  const handleStatus = async (referralId: string, status: ReferralStatus) => {
    setUpdatingId(referralId);
    try {
      await updateStatus(referralId, status);
      await fetchIncoming();
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
        Incoming Referrals
      </h1>

      {error && <p className="text-sm text-[#DC2626]">{error}</p>}

      {loading && (
        <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white p-8 text-center text-slate-500 dark:text-slate-500">
          Loading...
        </div>
      )}

      {!loading && incoming.length === 0 && (
        <Card className="p-0">
          <EmptyState
            icon={<ArrowRightLeft className="h-12 w-12" />}
            title="No incoming referrals"
            description="There are currently no patient referrals directed to your facility."
          />
        </Card>
      )}

      {!loading && incoming.length > 0 && (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Patient (ID)</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">From facility</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Reason</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Date</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {incoming.map((r) => (
                  <tr key={r.referral_id} className="border-b border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900">
                    <td className="px-4 py-3 font-mono text-sm text-slate-500 dark:text-slate-500">{r.global_patient_id}</td>
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{r.from_facility_name}</td>
                    <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-500">{r.reason}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant[r.status]}>{r.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-500">{r.created_at}</td>
                    <td className="px-4 py-3 flex gap-2">
                      {r.status === "PENDING" && (
                        <>
                          <Button
                            size="sm"
                            disabled={updatingId === r.referral_id}
                            onClick={() => handleStatus(r.referral_id, "ACCEPTED")}
                          >
                            {updatingId === r.referral_id ? "..." : "Accept"}
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={updatingId === r.referral_id}
                            onClick={() => handleStatus(r.referral_id, "REJECTED")}
                          >
                            Reject
                          </Button>
                        </>
                      )}
                      {r.status === "ACCEPTED" && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={updatingId === r.referral_id}
                          onClick={() => handleStatus(r.referral_id, "COMPLETED")}
                        >
                          {updatingId === r.referral_id ? "..." : "Mark complete"}
                        </Button>
                      )}
                      <a href={`/cross-facility-records/${r.global_patient_id}`} className="text-[#0B8A96] hover:underline text-sm">
                        View records
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
