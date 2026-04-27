"use client";

import React, { useState, useCallback } from "react";
import { useShiftHandover } from "@/hooks/use-shift-handover";
import { Button } from "@/components/ui/button";
import { ShiftHandover } from "@/lib/types";

interface SignatureCaptureProps {
  handoverId: string;
  incomingNurseName: string;
  outgoingNurseName: string;
  onAcknowledgeSuccess: (handover: ShiftHandover) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function SignatureCapture({
  handoverId,
  incomingNurseName,
  outgoingNurseName,
  onAcknowledgeSuccess,
  onCancel,
  loading: externalLoading = false,
}: SignatureCaptureProps) {
  const { acknowledgeHandover, loading: hookLoading, error } = useShiftHandover();
  const loading = externalLoading || hookLoading;

  const [acknowledged, setAcknowledged] = useState(false);

  const handleAcknowledge = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!acknowledged) {
        return;
      }

      try {
        const handover = await acknowledgeHandover(handoverId, {
          acknowledgement: "I acknowledge receipt of this shift handover and understand the patient status and recommendations.",
        });

        onAcknowledgeSuccess(handover);
      } catch {
        // Error is handled by hook state and displayed in UI
      }
    },
    [handoverId, acknowledged, acknowledgeHandover, onAcknowledgeSuccess]
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6 max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Acknowledge Shift Handover</h2>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-800 text-sm font-medium">
            {error instanceof Error ? error.message : "Failed to acknowledge handover"}
          </p>
        </div>
      )}

      <form onSubmit={handleAcknowledge} className="space-y-6">
        {/* From and To */}
        <div className="bg-gray-50 p-4 rounded-md space-y-3">
          <div className="flex items-start">
            <span className="font-medium text-gray-700 w-20">From:</span>
            <span className="text-gray-900">{outgoingNurseName} (Outgoing Nurse)</span>
          </div>
          <div className="flex items-start">
            <span className="font-medium text-gray-700 w-20">To:</span>
            <span className="text-gray-900">{incomingNurseName} (Incoming Nurse)</span>
          </div>
        </div>

        {/* Info text */}
        <p className="text-gray-700 text-sm leading-relaxed">
          Please acknowledge receipt of this handover to confirm understanding of the patient status,
          medical history, current assessment, and recommended actions.
        </p>

        {/* Checkbox */}
        <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-md">
          <input
            type="checkbox"
            id="acknowledge-checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            disabled={loading}
            className="w-5 h-5 mt-0.5 cursor-pointer rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-200"
          />
          <label
            htmlFor="acknowledge-checkbox"
            className="text-sm text-gray-800 flex-1 cursor-pointer leading-relaxed"
          >
            I acknowledge receipt of this shift handover and understand the patient status and
            recommendations.
          </label>
        </div>

        {/* Buttons */}
        <div className="flex gap-3 pt-6">
          <Button
            type="submit"
            disabled={!acknowledged || loading}
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Confirming...
              </span>
            ) : (
              "Acknowledge"
            )}
          </Button>
          <Button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-md disabled:bg-gray-100 disabled:cursor-not-allowed"
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
