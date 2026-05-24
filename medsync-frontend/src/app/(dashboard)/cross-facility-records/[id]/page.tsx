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

  const [breakGlassReasonCode, setBreakGlassReasonCode] = useState("life_threatening_emergency");
  const [breakGlassReason, setBreakGlassReason] = useState("");
  const [showBreakGlassForm, setShowBreakGlassForm] = useState(false);
  const [breakGlassConfirmOpen, setBreakGlassConfirmOpen] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [timeLeft, setTimeLeft] = useState<string | null>(null);

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

  useEffect(() => {
    if (!data?.expires_at) {
      queueMicrotask(() => setTimeLeft(null));
      return;
    }

    const interval = setInterval(() => {
      const expires = new Date(data.expires_at!).getTime();
      const now = new Date().getTime();
      const diff = expires - now;

      if (diff <= 0) {
        setTimeLeft("Expired");
        clearInterval(interval);
      } else {
        const h = Math.floor(diff / (1000 * 60 * 60));
        const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const s = Math.floor((diff % (1000 * 60)) / 1000);
        setTimeLeft(`${h}h ${m}m ${s}s`);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [data?.expires_at]);

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
    if (!breakGlassReason.trim() || !breakGlassReasonCode) return;
    try {
      await breakGlass({
        global_patient_id: id,
        reason_code: breakGlassReasonCode,
        reason: breakGlassReason.trim(),
      });
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
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-900 dark:text-slate-100">
                  Reason code (required)
                </label>
                <select
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
                  value={breakGlassReasonCode}
                  onChange={(e) => setBreakGlassReasonCode(e.target.value)}
                >
                  <option value="life_threatening_emergency">Life-threatening emergency</option>
                  <option value="unconscious_patient">Unconscious patient</option>
                  <option value="legal_requirement">Legal/Court requirement</option>
                  <option value="other">Other emergency</option>
                </select>
              </div>
              <Input
                label="Detail (required)"
                value={breakGlassReason}
                onChange={(e) => setBreakGlassReason(e.target.value)}
                placeholder="Describe the clinical emergency..."
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
            {timeLeft && (
              <div className={`mt-3 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                timeLeft === "Expired" ? "bg-red-100 text-red-800" : "bg-orange-100 text-orange-800"
              }`}>
                <svg className="mr-1.5 h-2 w-2 animate-pulse text-orange-400" fill="currentColor" viewBox="0 0 8 8">
                  <circle cx="4" cy="4" r="3" />
                </svg>
                Access Expires In: {timeLeft}
              </div>
            )}
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
