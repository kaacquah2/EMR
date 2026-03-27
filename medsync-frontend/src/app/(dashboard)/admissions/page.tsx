"use client";

import React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useAdmissions } from "@/hooks/use-admissions";
import { Card } from "@/components/ui/card";

export default function AdmissionsListPage() {
  const { user } = useAuth();
  const { admissions, loading } = useAdmissions();

  const allowed = ["doctor", "hospital_admin", "nurse", "super_admin"].includes(user?.role ?? "");
  if (!allowed) {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to view admissions.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
        {user?.role === "nurse" ? "Ward Patients" : "Active Admissions"}
      </h1>

      <Card className="p-6">
        {loading ? (
          <p className="text-[#64748B]">Loading...</p>
        ) : admissions.length === 0 ? (
          <p className="text-[#64748B]">No active admissions.</p>
        ) : (
          <div className="space-y-2">
            {admissions.map((a) => (
              <Link
                key={a.admission_id}
                href={`/patients/${a.patient_id}`}
                className="flex items-center justify-between rounded-lg border border-[#E2E8F0] p-4 hover:bg-[#F8FAFC]"
              >
                <div>
                  <p className="font-medium">{a.patient_name}</p>
                  <p className="text-sm text-[#64748B]">
                    {a.ghana_health_id} • {a.ward_name}{a.bed_code ? ` • Bed ${a.bed_code}` : ""} • Admitted {a.admitted_at?.slice(0, 10)} by {a.admitted_by}
                  </p>
                </div>
                <span className="text-sm text-[#0B8A96]">View patient</span>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
