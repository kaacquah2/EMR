"use client";

import React, { useState, useCallback } from "react";
import { useShiftHandover } from "@/hooks/use-shift-handover";
import { User, ShiftHandover } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";

interface ShiftHandoverFormProps {
  shiftId: string;
  onSubmitSuccess: (handover: ShiftHandover) => void;
  onCancel: () => void;
  incomingNurses: User[];
  loading?: boolean;
}

export function ShiftHandoverForm({
  shiftId,
  onSubmitSuccess,
  onCancel,
  incomingNurses,
  loading: externalLoading = false,
}: ShiftHandoverFormProps) {
  const { submitHandover, loading: hookLoading, error } = useShiftHandover();
  const loading = externalLoading || hookLoading;

  const [form, setForm] = useState({
    situation: "",
    background: "",
    assessment: "",
    recommendation: "",
    incoming_nurse_id: "",
  });

  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const validateForm = useCallback((): boolean => {
    const errors: Record<string, string> = {};

    if (!form.situation.trim()) {
      errors.situation = "Situation is required";
    }
    if (!form.background.trim()) {
      errors.background = "Background is required";
    }
    if (!form.assessment.trim()) {
      errors.assessment = "Assessment is required";
    }
    if (!form.recommendation.trim()) {
      errors.recommendation = "Recommendation is required";
    }
    if (!form.incoming_nurse_id.trim()) {
      errors.incoming_nurse_id = "Incoming nurse is required";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [form]);

  const handleFieldChange = useCallback(
    (field: keyof typeof form, value: string) => {
      setForm((prev) => ({
        ...prev,
        [field]: value,
      }));
      // Clear validation error for this field when user starts typing
      if (validationErrors[field]) {
        setValidationErrors((prev) => {
          const newErrors = { ...prev };
          delete newErrors[field];
          return newErrors;
        });
      }
    },
    [validationErrors]
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      try {
        const handover = await submitHandover({
          shift_id: shiftId,
          situation: form.situation,
          background: form.background,
          assessment: form.assessment,
          recommendation: form.recommendation,
          incoming_nurse_id: form.incoming_nurse_id,
        });

        setForm({
          situation: "",
          background: "",
          assessment: "",
          recommendation: "",
          incoming_nurse_id: "",
        });
        setValidationErrors({});

        onSubmitSuccess(handover);
      } catch {
        // Error is handled by hook state and displayed in UI
      }
    },
    [shiftId, form, submitHandover, validateForm, onSubmitSuccess]
  );

  const isFormComplete =
    form.situation.trim() &&
    form.background.trim() &&
    form.assessment.trim() &&
    form.recommendation.trim() &&
    form.incoming_nurse_id.trim();

  return (
    <div className="bg-white rounded-lg shadow-md p-6 max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">SBAR Shift Handover</h2>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-800 text-sm font-medium">
            {error instanceof Error ? error.message : "Failed to submit handover"}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Situation */}
        <Textarea
          id="situation"
          label="Situation"
          value={form.situation}
          onChange={(e) => handleFieldChange("situation", e.target.value)}
          placeholder="What's the status of the patient?"
          maxLength={2000}
          showCount
          error={validationErrors.situation}
          disabled={loading}
        />
        <p className="text-xs text-gray-500 -mt-3 mb-2">Overview of patient, key events...</p>

        {/* Background */}
        <Textarea
          id="background"
          label="Background"
          value={form.background}
          onChange={(e) => handleFieldChange("background", e.target.value)}
          placeholder="What's the context behind this patient's condition?"
          maxLength={2000}
          showCount
          error={validationErrors.background}
          disabled={loading}
        />
        <p className="text-xs text-gray-500 -mt-3 mb-2">Medical history, relevant facts...</p>

        {/* Assessment */}
        <Textarea
          id="assessment"
          label="Assessment"
          value={form.assessment}
          onChange={(e) => handleFieldChange("assessment", e.target.value)}
          placeholder="What's the current clinical concern?"
          maxLength={2000}
          showCount
          error={validationErrors.assessment}
          disabled={loading}
        />
        <p className="text-xs text-gray-500 -mt-3 mb-2">Current clinical status, risks...</p>

        {/* Recommendation */}
        <Textarea
          id="recommendation"
          label="Recommendation"
          value={form.recommendation}
          onChange={(e) => handleFieldChange("recommendation", e.target.value)}
          placeholder="What should happen next?"
          maxLength={2000}
          showCount
          error={validationErrors.recommendation}
          disabled={loading}
        />
        <p className="text-xs text-gray-500 -mt-3 mb-2">Suggested actions, priorities...</p>

        {/* Incoming Nurse */}
        <Select
          id="incoming_nurse"
          label="Incoming Nurse"
          value={form.incoming_nurse_id}
          onChange={(e) => handleFieldChange("incoming_nurse_id", e.target.value)}
          error={validationErrors.incoming_nurse_id}
          disabled={loading}
        >
          <option value="">Select nurse...</option>
          {incomingNurses.map((nurse) => (
            <option key={nurse.user_id} value={nurse.user_id}>
              {nurse.full_name}
            </option>
          ))}
        </Select>
        <p className="text-xs text-gray-500 -mt-3 mb-2">Who&apos;s receiving this handover?</p>

        {/* Buttons */}
        <div className="flex gap-3 pt-6">
          <Button
            type="submit"
            loading={loading}
            disabled={!isFormComplete}
            fullWidth
          >
            Submit Handover
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={loading}
            fullWidth
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
