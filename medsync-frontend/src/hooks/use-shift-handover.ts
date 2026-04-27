"use client";

import { useCallback, useState } from "react";
import { useApi } from "./use-api";

export interface SubmitHandoverPayload {
  shift_id: string;
  situation: string;
  background: string;
  assessment: string;
  recommendation: string;
  incoming_nurse_id: string;
}

export interface AcknowledgePayload {
  acknowledgement: string;
}

export interface ShiftHandover {
  id: string;
  shift_id: string;
  outgoing_nurse_id: string;
  incoming_nurse_id: string;
  situation: string;
  background: string;
  assessment: string;
  recommendation: string;
  outgoing_signed_at: string;
  incoming_acknowledged_at: string | null;
  status: "pending" | "acknowledged";
  created_at: string;
}

export function useShiftHandover() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [handover, setHandover] = useState<ShiftHandover | null>(null);

  const submitHandover = useCallback(
    async (data: SubmitHandoverPayload): Promise<ShiftHandover> => {
      setLoading(true);
      setError(null);
      try {
        const payload = {
          situation: data.situation,
          background: data.background,
          assessment: data.assessment,
          recommendation: data.recommendation,
          incoming_nurse_id: data.incoming_nurse_id,
        };

        const response = await api.post<ShiftHandover>(
          `/nurse/shift/${data.shift_id}/handover`,
          payload
        );

        setHandover(response);
        return response;
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Failed to submit handover");
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const acknowledgeHandover = useCallback(
    async (handoverId: string, acknowledgeData: AcknowledgePayload): Promise<ShiftHandover> => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.post<ShiftHandover>(
          `/nurse/shift-handover/${handoverId}/acknowledge`,
          acknowledgeData
        );

        setHandover(response);
        return response;
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Failed to acknowledge handover");
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return {
    submitHandover,
    acknowledgeHandover,
    loading,
    error,
    handover,
  };
}
