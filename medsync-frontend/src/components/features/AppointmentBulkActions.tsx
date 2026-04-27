"use client";

import React, { useState, useMemo } from "react";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Calendar, Clock, Trash2, CheckCircle } from "lucide-react";

interface Appointment {
  id: string;
  patient_name: string;
  ghana_health_id: string;
  scheduled_at: string;
  status: string;
}

interface AppointmentBulkActionsProps {
  appointments: Appointment[];
  onRefresh?: () => Promise<void>;
}

export default function AppointmentBulkActions({
  appointments,
  onRefresh,
}: AppointmentBulkActionsProps) {
  const api = useApi();
  const toast = useToast();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [actionMode, setActionMode] = useState<"reschedule" | "cancel" | null>(null);
  const [rescheduleTo, setRescheduleTo] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [processing, setProcessing] = useState(false);
  const [processResults, setProcessResults] = useState<{
    successful: string[];
    failed: Array<{ id: string; error: string }>;
  } | null>(null);

  const selectableAppointments = useMemo(
    () => appointments.filter((apt) => apt.status === "scheduled"),
    [appointments]
  );

  const handleToggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedIds.size === selectableAppointments.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(selectableAppointments.map((apt) => apt.id)));
    }
  };

  const handleReschedule = async () => {
    if (!rescheduleTo) {
      toast.error("Please select a new date and time");
      return;
    }

    setProcessing(true);
    const results = { successful: [] as string[], failed: [] as Array<{ id: string; error: string }> };

    for (const aptId of selectedIds) {
      try {
        const dt = new Date(rescheduleTo);
        const isoString = dt.toISOString();

        await api.post(`/appointments/${aptId}/reschedule`, {
          scheduled_at: isoString,
          reason: "Bulk rescheduled by receptionist",
        });
        results.successful.push(aptId);
      } catch (err) {
        results.failed.push({
          id: aptId,
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }

    setProcessResults(results);
    setProcessing(false);

    if (results.failed.length === 0) {
      toast.success(`${results.successful.length} appointment(s) rescheduled`);
      setSelectedIds(new Set());
      setActionMode(null);
      setRescheduleTo("");
      if (onRefresh) await onRefresh();
    } else {
      toast.error(
        `${results.successful.length} succeeded, ${results.failed.length} failed`
      );
    }
  };

  const handleCancel = async () => {
    if (!cancelReason.trim()) {
      toast.error("Please provide a cancellation reason");
      return;
    }

    setProcessing(true);
    const results = { successful: [] as string[], failed: [] as Array<{ id: string; error: string }> };

    for (const aptId of selectedIds) {
      try {
        await api.delete(`/appointments/${aptId}/delete`, {
          cancellation_reason: cancelReason,
        });
        results.successful.push(aptId);
      } catch (err) {
        results.failed.push({
          id: aptId,
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }

    setProcessResults(results);
    setProcessing(false);

    if (results.failed.length === 0) {
      toast.success(`${results.successful.length} appointment(s) cancelled`);
      setSelectedIds(new Set());
      setActionMode(null);
      setCancelReason("");
      if (onRefresh) await onRefresh();
    } else {
      toast.error(
        `${results.successful.length} succeeded, ${results.failed.length} failed`
      );
    }
  };

  if (selectableAppointments.length === 0) {
    return (
      <Card className="p-6 bg-slate-50">
        <p className="text-[#64748B]">No scheduled appointments available for bulk operations</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Results Summary */}
      {processResults && (
        <Card className={`p-4 ${processResults.failed.length === 0 ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"}`}>
          <div className="flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-green-900">Operation completed</p>
              <p className="text-sm text-green-800 mt-1">
                {processResults.successful.length} successful
                {processResults.failed.length > 0 && `, ${processResults.failed.length} failed`}
              </p>
              {processResults.failed.length > 0 && (
                <div className="mt-3 bg-white rounded p-3 text-sm space-y-1 max-h-40 overflow-y-auto">
                  {processResults.failed.map((item, idx) => (
                    <div key={idx} className="text-red-700">
                      <span className="font-medium">{appointments.find((a) => a.id === item.id)?.patient_name}:</span> {item.error}
                    </div>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={() => setProcessResults(null)}
                className="mt-2 text-sm text-green-700 underline hover:no-underline"
              >
                Clear
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Selection & Actions */}
      <Card className="p-6">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h3 className="font-sora text-lg font-bold text-[#0F172A]">
              Bulk Operations ({selectedIds.size} selected)
            </h3>
            {selectedIds.size > 0 && (
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                className="text-sm text-[#0EAFBE] hover:underline"
              >
                Clear selection
              </button>
            )}
          </div>

          {/* Actions */}
          {selectedIds.size > 0 && !actionMode && (
            <div className="flex gap-3">
              <Button
                onClick={() => setActionMode("reschedule")}
                className="flex items-center gap-2 bg-[#0EAFBE] hover:bg-[#0B94A6]"
              >
                <Calendar className="h-4 w-4" />
                Reschedule ({selectedIds.size})
              </Button>
              <Button
                onClick={() => setActionMode("cancel")}
                variant="outline"
                className="flex items-center gap-2 text-red-600 border-red-200 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
                Cancel ({selectedIds.size})
              </Button>
            </div>
          )}

          {/* Reschedule Form */}
          {actionMode === "reschedule" && (
            <div className="space-y-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div>
                <label className="block text-sm font-medium text-[#0F172A]">New Date & Time *</label>
                <Input
                  type="datetime-local"
                  value={rescheduleTo}
                  onChange={(e) => setRescheduleTo(e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleReschedule}
                  disabled={processing || !rescheduleTo}
                  className="bg-[#0EAFBE]"
                >
                  {processing ? "Processing..." : "Confirm Reschedule"}
                </Button>
                <Button
                  onClick={() => {
                    setActionMode(null);
                    setRescheduleTo("");
                  }}
                  variant="outline"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Cancel Form */}
          {actionMode === "cancel" && (
            <div className="space-y-3 p-4 bg-red-50 rounded-lg border border-red-200">
              <div>
                <label className="block text-sm font-medium text-[#0F172A]">Cancellation Reason *</label>
                <Input
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="e.g., Patient requested, Doctor unavailable"
                  className="mt-1"
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleCancel}
                  disabled={processing || !cancelReason.trim()}
                  className="bg-red-600 hover:bg-red-700"
                >
                  {processing ? "Processing..." : "Confirm Cancel"}
                </Button>
                <Button
                  onClick={() => {
                    setActionMode(null);
                    setCancelReason("");
                  }}
                  variant="outline"
                >
                  Back
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Selection List */}
      <Card className="p-6">
        <div className="space-y-3">
          {/* Select All Checkbox */}
          <div className="flex items-center gap-3 pb-3 border-b border-[#E2E8F0]">
            <input
              type="checkbox"
              checked={
                selectableAppointments.length > 0 && selectedIds.size === selectableAppointments.length
              }
              onChange={handleSelectAll}
              className="h-4 w-4 rounded border-[#CBD5E1]"
            />
            <span className="text-sm font-medium text-[#0F172A]">
              Select All ({selectableAppointments.length})
            </span>
          </div>

          {/* Appointment List */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {selectableAppointments.map((apt) => (
              <div
                key={apt.id}
                className="flex items-center gap-3 p-3 rounded-lg border border-[#E2E8F0] hover:bg-[#F8FAFC]"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(apt.id)}
                  onChange={() => handleToggleSelect(apt.id)}
                  className="h-4 w-4 rounded border-[#CBD5E1]"
                />
                <div className="flex-1">
                  <p className="font-medium text-[#0F172A]">{apt.patient_name}</p>
                  <p className="text-xs text-[#64748B]">{apt.ghana_health_id}</p>
                </div>
                <div className="flex items-center gap-2 text-sm text-[#64748B]">
                  <Clock className="h-4 w-4" />
                  {new Date(apt.scheduled_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
