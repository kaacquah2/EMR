"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useEffect } from "react";
import { Bed } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BedData } from "@/hooks/use-nurse-dashboard-enhanced";

interface BedGridProps {
  beds: BedData[];
  onMovePatient?: (patientId: string, fromBed: string, toBed: string) => void;
}

/**
 * Bed Grid Component - displays ward beds in 4-column grid
 * Each bed card shows: bed code, patient info, vitals status, clinical status, and action buttons
 */
export function BedGrid({ beds, onMovePatient }: BedGridProps) {
  return (
    <Card className="shadow-xl border-slate-200 dark:border-slate-800">
      <CardHeader>
        <CardTitle className="text-xl font-bold flex items-center gap-2">
          <Bed className="h-5 w-5 text-[#0EAFBE]" />
          Ward Bed Grid
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {beds.map((bed) => (
            <BedCard 
              key={bed.bed_code} 
              bed={bed} 
              onDropPatient={(patientId, fromBed) => onMovePatient?.(patientId, fromBed, bed.bed_code)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

interface BedCardProps {
  bed: BedData;
  onDropPatient: (patientId: string, fromBed: string) => void;
}

/**
 * Individual Bed Card - shows bed status with left border color coding
 */
function BedCard({ bed, onDropPatient }: BedCardProps) {
  const router = useRouter();
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    const initialFrame = requestAnimationFrame(() => setNow(Date.now()));
    const interval = setInterval(() => setNow(Date.now()), 60000);
    return () => {
      cancelAnimationFrame(initialFrame);
      clearInterval(interval);
    };
  }, []);

  const minutesSinceVitals = useMemo(() => {
    if (!bed.last_vitals_at || now === null) return null;
    return Math.round(
      (now - new Date(bed.last_vitals_at).getTime()) / (1000 * 60)
    );
  }, [bed.last_vitals_at, now]);

  const handleDragStart = (e: React.DragEvent) => {
    if (bed.status === "vacant") return;
    e.dataTransfer.setData("patientId", bed.patient_id!);
    e.dataTransfer.setData("fromBed", bed.bed_code);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (bed.status !== "vacant") return;
    e.preventDefault();
    setIsDraggingOver(true);
  };

  const handleDragLeave = () => {
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(false);
    const patientId = e.dataTransfer.getData("patientId");
    const fromBed = e.dataTransfer.getData("fromBed");
    if (patientId && fromBed && fromBed !== bed.bed_code) {
      onDropPatient(patientId, fromBed);
    }
  };

  const borderColorMap = {
    stable: "border-l-[#639922]",
    watch: "border-l-[#EF9F27]",
    critical: "border-l-[#E24B4A]",
    vacant: "border-l-0",
  };

  const bgColorMap = {
    stable: "bg-white dark:bg-slate-900",
    watch: "bg-white dark:bg-slate-900",
    critical: "bg-white dark:bg-slate-900",
    vacant: "bg-slate-50 dark:bg-slate-950/50",
  };

  if (bed.status === "vacant") {
    return (
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`rounded-xl border border-dashed p-4 h-full flex flex-col items-center justify-center transition-all ${
          isDraggingOver 
            ? "border-[#0EAFBE] bg-cyan-50/50 dark:bg-cyan-950/20 scale-105" 
            : "border-slate-200 dark:border-slate-800"
        } ${bgColorMap.vacant}`}
      >
        <p className="text-sm font-bold text-slate-400 dark:text-slate-600">{bed.bed_code}</p>
        <div className="mt-2 p-2 rounded-full bg-slate-100 dark:bg-slate-900">
          <Bed className="h-5 w-5 text-slate-300 dark:text-slate-700" />
        </div>
        <p className="mt-2 text-xs font-medium text-slate-400 uppercase tracking-tighter">Vacant</p>
      </div>
    );
  }

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className={`group relative rounded-xl border border-l-4 border-slate-200 dark:border-slate-800 ${bgColorMap[bed.status]} p-4 ${borderColorMap[bed.status]} shadow-sm hover:shadow-md transition-all cursor-grab active:cursor-grabbing`}
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
                router.push(`/worklist?patient=${bed.patient_id}`)
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
