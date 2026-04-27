"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BedData, PendingPrescription } from "@/hooks/use-nurse-dashboard-enhanced";

interface PriorityTasksPanelProps {
  beds: BedData[];
  prescriptions: PendingPrescription[];
}

/**
 * Priority Tasks Panel - shows urgent vitals due + pending dispense items
 * Sorted by: vitals overdue (longest first) → pending dispense
 */
export function PriorityTasksPanel({
  beds,
  prescriptions,
}: PriorityTasksPanelProps) {
  const router = useRouter();

  // Build task list
  const tasks: Array<{
    type: "VITALS" | "DISPENSE";
    patient_id: string;
    patient_name: string;
    bed_code: string | null;
    hours_overdue?: number;
    drug_name?: string;
    prescribed_by?: string;
  }> = [];

  // Add vitals overdue
  beds.forEach((bed) => {
    if (bed.vitals_overdue && bed.patient_id) {
      tasks.push({
        type: "VITALS",
        patient_id: bed.patient_id,
        patient_name: bed.patient_name || "Unknown",
        bed_code: bed.bed_code,
        hours_overdue: bed.vitals_overdue_hours || 0,
      });
    }
  });

  // Add pending dispense
  prescriptions.forEach((rx) => {
    tasks.push({
      type: "DISPENSE",
      patient_id: rx.patient_id,
      patient_name: rx.patient_name,
      bed_code: rx.bed_code,
      drug_name: rx.drug_name,
      prescribed_by: rx.prescribed_by,
    });
  });

  // Sort: vitals (by hours overdue DESC) then dispense
  tasks.sort((a, b) => {
    if (a.type !== b.type) {
      return a.type === "VITALS" ? -1 : 1;
    }
    if (a.type === "VITALS") {
      return (b.hours_overdue || 0) - (a.hours_overdue || 0);
    }
    return 0;
  });

  const hasUrgent = tasks.length > 0;

  return (
    <Card className={hasUrgent ? "border-red-200" : ""}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-lg">
          <span>Priority tasks</span>
          {hasUrgent && (
            <Badge variant="critical" className="text-xs">
              {tasks.length} urgent
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tasks.length === 0 ? (
          <p className="text-sm text-slate-500">No urgent tasks</p>
        ) : (
          <div className="space-y-3">
            {tasks.map((task, idx) => (
              <div
                key={`${task.type}-${task.patient_id}-${idx}`}
                className="border-b border-slate-100 pb-3 last:border-b-0 last:pb-0"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={task.type === "VITALS" ? "critical" : "pending"}
                        className="text-xs"
                      >
                        {task.type === "VITALS" ? "Vitals due" : "Dispense"}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                      {task.patient_name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {task.bed_code}
                      {task.type === "VITALS"
                        ? ` · ${task.hours_overdue}h overdue`
                        : ` · ${task.drug_name}`}
                      {task.prescribed_by && ` · ${task.prescribed_by}`}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs"
                    onClick={() => {
                      if (task.type === "VITALS") {
                        router.push(`/patients/${task.patient_id}/vitals/new`);
                      } else {
                        router.push(
                          `/worklist/dispense?patient=${task.patient_id}`
                        );
                      }
                    }}
                  >
                    {task.type === "VITALS" ? "Record →" : "Dispense →"}
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
