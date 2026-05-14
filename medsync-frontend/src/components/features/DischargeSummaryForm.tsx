"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { Encounter } from "@/lib/types";

const DISCHARGE_TEMPLATE = `Diagnosis:
Treatment given:
Follow-up:
Medications on discharge:
`;

interface DischargeSummaryFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  encounters: Encounter[];
  patientId: string;
  onSave: (encounterId: string, dischargeSummary: string) => Promise<void>;
  onSuccess?: () => void;
}

export function DischargeSummaryForm({
  open,
  onOpenChange,
  encounters,
  onSave,
  onSuccess,
}: DischargeSummaryFormProps) {
  const [selectedEncounterId, setSelectedEncounterId] = useState<string>("");
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleUseTemplate = () => {
    setSummary((prev) => (prev ? prev + "\n\n" + DISCHARGE_TEMPLATE : DISCHARGE_TEMPLATE));
  };

  const handleSave = async () => {
    if (!selectedEncounterId || !summary.trim()) {
      setError("Select an encounter and enter a discharge summary.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await onSave(selectedEncounterId, summary.trim());
      setSummary("");
      setSelectedEncounterId("");
      onOpenChange(false);
      onSuccess?.();
    } catch {
      setError("Failed to save discharge summary.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setError("");
      setSummary("");
      setSelectedEncounterId("");
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogPortal>
        <DialogOverlay />
        <DialogContent size="lg" className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Discharge summary</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Encounter</label>
              <select
                value={selectedEncounterId}
                onChange={(e) => {
                  setSelectedEncounterId(e.target.value);
                  const enc = encounters.find((x) => x.id === e.target.value);
                  setSummary(enc?.discharge_summary || "");
                }}
                className="w-full rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 text-sm"
              >
                <option value="">Select encounter</option>
                {encounters.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.encounter_type} — {e.encounter_date ? new Date(e.encounter_date).toLocaleString() : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Summary</label>
                <Button type="button" variant="ghost" size="sm" onClick={handleUseTemplate}>
                  Use template
                </Button>
              </div>
              <Textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={12}
                placeholder="Enter discharge summary..."
                showCount
                maxLength={4000}
              />
            </div>
            {error && <p className="text-sm text-[#DC2626]">{error}</p>}
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={loading}>
                {loading ? "Saving..." : "Save"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
}
