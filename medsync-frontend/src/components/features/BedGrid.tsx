"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BedData } from "@/hooks/use-nurse-dashboard-enhanced";

interface BedGridProps {
  beds: BedData[];
}

/**
 * Bed Grid Component - displays ward beds in 4-column grid
 * Each bed card shows: bed code, patient info, vitals status, clinical status, and action buttons
 */
export function BedGrid({ beds }: BedGridProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ward 3B — bed overview</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {beds.map((bed) => (
            <BedCard key={bed.bed_code} bed={bed} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

interface BedCardProps {
  bed: BedData;
}

/**
 * Individual Bed Card - shows bed status with left border color coding
 */
function BedCard({ bed }: BedCardProps) {
  const router = useRouter();
  // Track current time for calculating vitals age - initialized lazily
  const [now, setNow] = useState<number | null>(null);

  // Initialize time on mount and update periodically
  useEffect(() => {
    // Use requestAnimationFrame to defer the initial setState
    const initialFrame = requestAnimationFrame(() => setNow(Date.now()));
    const interval = setInterval(() => setNow(Date.now()), 60000); // Update every minute
    return () => {
      cancelAnimationFrame(initialFrame);
      clearInterval(interval);
    };
  }, []);

  // Compute minutes since last vitals using pure calculation
  const minutesSinceVitals = useMemo(() => {
    if (!bed.last_vitals_at || now === null) return null;
    return Math.round(
      (now - new Date(bed.last_vitals_at).getTime()) / (1000 * 60)
    );
  }, [bed.last_vitals_at, now]);

  // Border color based on status
  const borderColorMap = {
    stable: "border-l-[#639922]",    // green
    watch: "border-l-[#EF9F27]",     // amber
    critical: "border-l-[#E24B4A]",  // red
    vacant: "border-l-0",
  };

  const bgColorMap = {
    stable: "bg-white",
    watch: "bg-white",
    critical: "bg-white",
    vacant: "bg-slate-50",
  };

  if (bed.status === "vacant") {
    return (
      <div
        className={`rounded-lg border border-slate-200 ${bgColorMap.vacant} p-3 ${borderColorMap.vacant}`}
      >
        <p className="text-sm font-medium text-slate-500">{bed.bed_code}</p>
        <p className="mt-2 text-xs text-slate-400">Vacant</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border border-l-4 border-slate-200 ${bgColorMap[bed.status]} p-3 ${borderColorMap[bed.status]}`}
    >
      {/* Bed Code */}
      <p className="text-sm font-semibold text-slate-900">{bed.bed_code}</p>

      {/* Patient Info */}
      <div className="mt-2 space-y-1">
        <p className="text-sm font-medium text-slate-900">{bed.patient_name}</p>
        <p className="text-xs text-slate-600">
          {bed.age}y · {bed.gender}
        </p>
      </div>

      {/* Vitals Status */}
      <div className="mt-3 border-t border-slate-100 pt-2">
        {bed.vitals_overdue ? (
          <p className="text-xs font-medium text-red-600">
            Vitals overdue {bed.vitals_overdue_hours}h
          </p>
        ) : minutesSinceVitals !== null ? (
          <p className="text-xs text-slate-500">
            Vitals {minutesSinceVitals}m ago · OK
          </p>
        ) : (
          <p className="text-xs text-slate-400">No vitals recorded</p>
        )}
      </div>

      {/* Active Alerts Badge */}
      {bed.active_alerts_count > 0 && (
        <div className="mt-2">
          <Badge variant="critical" className="text-xs">
            {bed.active_alerts_count} alert
            {bed.active_alerts_count !== 1 ? "s" : ""}
          </Badge>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-3 space-y-2">
        <Button
          size="sm"
          variant="secondary"
          className="w-full text-xs"
          onClick={() => router.push(`/patients/${bed.patient_id}/vitals/new`)}
        >
          Vitals
        </Button>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            className="flex-1 text-xs"
            onClick={() => router.push(`/patients/${bed.patient_id}`)}
          >
            Chart
          </Button>
          {bed.pending_dispense_count > 0 && (
            <Button
              size="sm"
              variant="ghost"
              className="flex-1 text-xs"
              onClick={() =>
                router.push(`/worklist/dispense?patient=${bed.patient_id}`)
              }
            >
              Dispense
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="flex-1 text-xs"
            onClick={() =>
              router.push(`/records/nursing-note?patient=${bed.patient_id}`)
            }
          >
            Note
          </Button>
        </div>
      </div>
    </div>
  );
}
