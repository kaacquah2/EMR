"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useReferrals } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ReferralStatus } from "@/lib/types";

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

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

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
      <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
        Incoming Referrals
      </h1>

      {error && <p className="text-sm text-[#DC2626]">{error}</p>}

      {loading && (
        <div className="rounded-lg border border-[#CBD5E1] bg-white p-8 text-center text-[#64748B]">
          Loading...
        </div>
      )}

      {!loading && incoming.length === 0 && (
        <Card className="p-8 text-center">
          <p className="text-[#64748B]">No incoming referrals.</p>
        </Card>
      )}

      {!loading && incoming.length > 0 && (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Patient (ID)</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">From facility</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Reason</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Date</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {incoming.map((r) => (
                  <tr key={r.referral_id} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3 font-mono text-sm text-[#64748B]">{r.global_patient_id}</td>
                    <td className="px-4 py-3 font-medium text-[#0F172A]">{r.from_facility_name}</td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">{r.reason}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant[r.status]}>{r.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">{r.created_at}</td>
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
