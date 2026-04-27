"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/hooks/use-api";
import { SignatureCapture } from "@/components/features/nurse/signature-capture";
import { ShiftHandover } from "@/lib/types";

interface PageProps {
  params: {
    handoverId: string;
  };
}

export default function AcknowledgeShiftHandoverPage({ params }: PageProps) {
  const { handoverId } = params;
  const router = useRouter();
  const api = useApi();

  const [handover, setHandover] = useState<ShiftHandover | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadHandover = async () => {
      try {
        const response = await api.get<ShiftHandover>(
          `/nurse/shift-handover/${handoverId}`
        );
        setHandover(response);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load handover details"
        );
      } finally {
        setLoading(false);
      }
    };

    loadHandover();
  }, [handoverId, api]);

  const handleAcknowledgeSuccess = () => {
    router.push("/dashboard");
  };

  const handleCancel = () => {
    router.back();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600"></div>
      </div>
    );
  }

  if (error || !handover) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800 text-sm font-medium">{error || "Handover not found"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Acknowledge Shift Handover</h1>
          <p className="mt-2 text-gray-600">
            Review the handover details below before acknowledging.
          </p>
        </div>

        {/* Handover Details - Read Only */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Handover Details</h2>

          <div className="space-y-4">
            {/* Situation */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Situation
              </label>
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                <p className="text-gray-900 text-sm whitespace-pre-wrap font-mono">
                  {handover.situation}
                </p>
              </div>
            </div>

            {/* Background */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Background
              </label>
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                <p className="text-gray-900 text-sm whitespace-pre-wrap font-mono">
                  {handover.background}
                </p>
              </div>
            </div>

            {/* Assessment */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Assessment
              </label>
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                <p className="text-gray-900 text-sm whitespace-pre-wrap font-mono">
                  {handover.assessment}
                </p>
              </div>
            </div>

            {/* Recommendation */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Recommendation
              </label>
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                <p className="text-gray-900 text-sm whitespace-pre-wrap font-mono">
                  {handover.recommendation}
                </p>
              </div>
            </div>

            {/* Metadata */}
            <div className="pt-4 border-t border-gray-200">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <label className="text-gray-600">Outgoing Nurse</label>
                  <p className="text-gray-900 font-medium">{handover.outgoing_nurse_id}</p>
                </div>
                <div>
                  <label className="text-gray-600">Signed At</label>
                  <p className="text-gray-900 font-medium">
                    {new Date(handover.outgoing_signed_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Signature Capture */}
        <SignatureCapture
          handoverId={handoverId}
          incomingNurseName={handover.incoming_nurse_id}
          outgoingNurseName={handover.outgoing_nurse_id}
          onAcknowledgeSuccess={handleAcknowledgeSuccess}
          onCancel={handleCancel}
        />
      </div>
    </div>
  );
}
