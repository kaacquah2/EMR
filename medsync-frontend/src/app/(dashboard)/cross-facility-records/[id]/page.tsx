"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useCrossFacilityRecords, useBreakGlass } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RecordTimelineCard } from "@/components/features/RecordTimelineCard";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export default function CrossFacilityRecordsPage() {
  const params = useParams();
  const id = params.id as string;
  const { user } = useAuth();
  const { data, loading, error, fetch } = useCrossFacilityRecords();
  const { create: breakGlass, loading: breakGlassLoading } = useBreakGlass();

  const [breakGlassReason, setBreakGlassReason] = useState("");
  const [showBreakGlassForm, setShowBreakGlassForm] = useState(false);
  const [breakGlassConfirmOpen, setBreakGlassConfirmOpen] = useState(false);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    if (!id) return;
    queueMicrotask(() => setForbidden(false));
    fetch(id).catch((err) => {
      const msg = (err?.message || "").toLowerCase();
      if (/no consent|break-glass|denied|forbidden|403/.test(msg)) {
        setForbidden(true);
      }
    });
  }, [id, fetch]);

  const canView =
    user?.role === "doctor" ||
    user?.role === "hospital_admin" ||
    user?.role === "super_admin";

  if (!canView) {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to view cross-facility records.
      </div>
    );
  }

  const handleBreakGlass = async () => {
    if (!breakGlassReason.trim()) return;
    try {
      await breakGlass({ global_patient_id: id, reason: breakGlassReason.trim() });
      setShowBreakGlassForm(false);
      setBreakGlassReason("");
      setBreakGlassConfirmOpen(false);
      await fetch(id);
      setForbidden(false);
    } catch {
      // error state in hook
    }
  };

  const facilityNameById = (facilityId: string) => {
    const f = data?.facilities?.find((x) => x.facility_id === facilityId);
    return f?.name ?? facilityId;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
          Cross-facility records
        </h1>
        <Link href="/patients/search">
          <Button variant="secondary">Back to search</Button>
        </Link>
      </div>

      {loading && (
        <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white p-8 text-center text-slate-500 dark:text-slate-500">
          Loading...
        </div>
      )}

      {error && !forbidden && (
        <div className="rounded-lg bg-[#FEE2E2] p-4 text-[#B91C1C]">
          {error}
        </div>
      )}

      {forbidden && !data && (
        <Card className="p-6">
          <p className="text-slate-500 dark:text-slate-500 mb-4">
            You do not have consent to view this patient&apos;s records. Request emergency access (break-glass)?
          </p>
          {!showBreakGlassForm ? (
            <Button onClick={() => setShowBreakGlassForm(true)}>
              Request emergency access
            </Button>
          ) : (
            <div className="space-y-4">
              <Input
                label="Reason for emergency access (required)"
                value={breakGlassReason}
                onChange={(e) => setBreakGlassReason(e.target.value)}
                placeholder="e.g. Emergency presentation, life-threatening"
              />
              <div className="flex gap-2">
                <Button
                  disabled={!breakGlassReason.trim() || breakGlassLoading}
                  onClick={() => setBreakGlassConfirmOpen(true)}
                >
                  {breakGlassLoading ? "Submitting..." : "Submit and view records"}
                </Button>
                <Button variant="secondary" onClick={() => setShowBreakGlassForm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      <ConfirmDialog
        open={breakGlassConfirmOpen}
        onOpenChange={setBreakGlassConfirmOpen}
        title="Confirm emergency access"
        message="This action will be logged and audited. You will gain temporary access to view this patient's records without consent. Continue?"
        confirmLabel="Submit and view records"
        variant="danger"
        loading={breakGlassLoading}
        onConfirm={handleBreakGlass}
      />

      {data && (
        <>
          <Card className="p-4">
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
              {data.demographics.full_name} — {data.demographics.national_id ?? "No national ID"}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
              DOB: {data.demographics.date_of_birth} | Scope: {data.scope} | Read-only
            </p>
            {data.facilities?.length > 0 && (
              <p className="text-xs text-slate-500 dark:text-slate-500 mt-2">
                Facilities: {data.facilities.map((f) => f.name).join(", ")}
              </p>
            )}
          </Card>

          {data.records && data.records.length > 0 ? (
            <div className="space-y-4">
              <h2 className="font-sora text-lg font-semibold text-slate-900 dark:text-slate-100">Records</h2>
              {data.records.map((r) => (
                <RecordTimelineCard
                  key={r.record_id}
                  record={r}
                  hospitalName={r.hospital_id ? facilityNameById(r.hospital_id) : undefined}
                />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 dark:text-slate-500">No records to display for this scope.</p>
          )}
        </>
      )}
    </div>
  );
}
