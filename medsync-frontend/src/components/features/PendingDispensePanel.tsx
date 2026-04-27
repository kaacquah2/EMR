"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";
import { useApi } from "@/hooks/use-api";
import { PendingPrescription } from "@/hooks/use-nurse-dashboard-enhanced";

interface PendingDispensePanelProps {
  prescriptions: PendingPrescription[];
  onRefresh: () => void;
}

/**
 * Pending Medication Dispense Panel - inline Mark dispensed action
 * Shows allergy conflict badge with tooltip
 */
export function PendingDispensePanel({
  prescriptions,
  onRefresh,
}: PendingDispensePanelProps) {
  const api = useApi();
  const toast = useToast();
  const [dispensing, setDispensing] = useState<Set<string>>(new Set());

  const handleMarkDispensed = async (prescriptionId: string, drugName: string) => {
    setDispensing((prev) => new Set([...prev, prescriptionId]));
    try {
      await api.post(
        `/records/prescription/${prescriptionId}/dispense`
      );
      toast.success(`Dispensed — ${drugName}`);
      onRefresh();
    } catch {
      toast.error("Failed to mark as dispensed");
    } finally {
      setDispensing((prev) => {
        const next = new Set(prev);
        next.delete(prescriptionId);
        return next;
      });
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pending medication dispense</CardTitle>
        <Button
          size="sm"
          variant="ghost"
          className="text-xs text-blue-600 hover:text-blue-700"
          onClick={() => window.location.href = "/worklist/dispense"}
        >
          View all →
        </Button>
      </CardHeader>
      <CardContent>
        {prescriptions.length === 0 ? (
          <p className="text-sm text-slate-500">No pending medications</p>
        ) : (
          <div className="space-y-4">
            {prescriptions.map((rx) => (
              <div
                key={rx.prescription_id}
                className="rounded-lg border border-slate-200 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-slate-900">
                        {rx.drug_name} {rx.dosage} — {rx.route}
                      </p>
                      {rx.allergy_conflict && (
                        <span
                          className="group relative inline-block cursor-help"
                          title={`Override authorised by ${rx.allergy_override_by}: ${rx.allergy_override_reason}`}
                        >
                          <Badge variant="critical" className="text-xs">
                            ⚠ Allergy conflict
                          </Badge>
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-xs text-slate-600">
                      {rx.patient_name} · {rx.bed_code} · {rx.prescribed_by} ·{" "}
                      {formatTimeAgo(new Date(rx.created_at))}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="text-xs"
                    data-testid={`dispense-button-${rx.prescription_id}`}
                    onClick={() =>
                      handleMarkDispensed(rx.prescription_id, rx.drug_name)
                    }
                    disabled={dispensing.has(rx.prescription_id)}
                  >
                    {dispensing.has(rx.prescription_id)
                      ? "Dispensing…"
                      : "Mark dispensed"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}
