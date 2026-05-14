"use client";

import React from "react";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const MIN_OVERRIDE_CHARS = 20;

export interface AllergyConflictInfo {
  allergen: string;
  reaction: string;
  severity: string;
}

interface AllergyConflictModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conflict: AllergyConflictInfo | null;
  drugName?: string;
  dosage?: string;
  overrideReason: string;
  onOverrideReasonChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function AllergyConflictModal({
  open,
  onOpenChange,
  conflict,
  drugName = "",
  dosage = "",
  overrideReason,
  onOverrideReasonChange,
  onConfirm,
  onCancel,
  loading = false,
}: AllergyConflictModalProps) {
  const canOverride = overrideReason.trim().length >= MIN_OVERRIDE_CHARS && !loading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay />
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle className="text-[#DC2626]">Drug-Allergy Conflict Detected</DialogTitle>
          </DialogHeader>
          {conflict && (
            <>
              <p className="text-sm text-slate-500 dark:text-slate-500">
                Patient allergy: <strong>{conflict.allergen}</strong>. Reaction: {conflict.reaction || "—"} ({conflict.severity || "—"}).
              </p>
              {(drugName || dosage) && (
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                  Your prescription: <strong>{[drugName, dosage].filter(Boolean).join(" ")}</strong>
                </p>
              )}
              <p className="text-sm text-slate-500 dark:text-slate-500 mt-2">
                This medication may cause a serious allergic reaction. Clinical override reason (min {MIN_OVERRIDE_CHARS} characters):
              </p>
              <Input
                label="Clinical Override Reason (required)"
                value={overrideReason}
                onChange={(e) => onOverrideReasonChange(e.target.value)}
                placeholder="Explain why prescribing despite conflict (min 20 characters)"
                className="mt-3"
              />
              {overrideReason.trim().length > 0 && overrideReason.trim().length < MIN_OVERRIDE_CHARS && (
                <p className="text-xs text-amber-600 mt-1">{MIN_OVERRIDE_CHARS - overrideReason.trim().length} more characters required.</p>
              )}
              <div className="mt-4 flex gap-2 justify-end">
                <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
                  Cancel Prescription
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  disabled={!canOverride}
                  onClick={onConfirm}
                >
                  {loading ? "Submitting..." : "Override & Prescribe"}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
}
