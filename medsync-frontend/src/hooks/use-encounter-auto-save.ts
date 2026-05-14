"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useApi } from "./use-api";
import type { EncounterDraft } from "@/lib/types";

export interface SOAPData {
  patient_id: string;
  encounter_id?: string;
  soap?: {
    subjective?: string;
    objective?: string;
    assessment?: string;
    plan?: string;
  };
  [key: string]: unknown;
}

export function useEncounterAutoSave(patientId: string | null, encounterId?: string | null) {
  const api = useApi();

  const [draft, setDraft] = useState<EncounterDraft | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // Refs for debounce and auto-save interval
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);
  const autoSaveTimer = useRef<NodeJS.Timeout | null>(null);
  const pendingData = useRef<SOAPData | null>(null);

  // Fetch existing draft on mount
  useEffect(() => {
    if (!patientId) return;

    const fetchDraft = async () => {
      try {
        const endpoint = encounterId
          ? `/patients/${patientId}/encounters/${encounterId}/draft`
          : `/patients/${patientId}/encounters/draft`;

        const response = await api.get<{ data: EncounterDraft }>(endpoint);
        if (response?.data) {
          const draftData = response.data;
          setDraft(draftData);
          setLastSavedAt(new Date(draftData.last_saved_at));
        }
      } catch {
        // No draft exists yet, which is fine
        setDraft(null);
      }
    };

    fetchDraft();
  }, [patientId, encounterId, api]);

  // Save draft to backend
  const saveDraftToBackend = useCallback(
    async (data: SOAPData) => {
      if (!patientId) return;

      setIsSaving(true);
      setError(null);

      try {
        const endpoint = encounterId
          ? `/patients/${patientId}/encounters/${encounterId}/draft`
          : `/patients/${patientId}/encounters/draft`;

        const method = draft ? "PATCH" : "POST";

        const response =
          method === "PATCH"
            ? await api.patch<{ data: EncounterDraft }>(endpoint, data)
            : await api.post<{ data: EncounterDraft }>(endpoint, data);

        if (response?.data) {
          const draftData = response.data;
          setDraft(draftData);
          setLastSavedAt(new Date(draftData.last_saved_at));
          pendingData.current = null;
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Failed to save draft");
        setError(error);
        console.error("Auto-save failed:", error);
      } finally {
        setIsSaving(false);
      }
    },
    [patientId, encounterId, draft, api]
  );

  // Debounced update (3 second debounce)
  const updateDraft = useCallback(
    (data: SOAPData) => {
      pendingData.current = data;

      // Clear existing debounce timer
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      // Set new debounce timer (3 seconds)
      debounceTimer.current = setTimeout(() => {
        if (pendingData.current) {
          saveDraftToBackend(pendingData.current);
        }
      }, 3000);
    },
    [saveDraftToBackend]
  );

  // Auto-save every 30 seconds
  useEffect(() => {
    if (!patientId) return;

    const startAutoSave = () => {
      autoSaveTimer.current = setInterval(() => {
        if (pendingData.current) {
          saveDraftToBackend(pendingData.current);
        }
      }, 30000); // 30 seconds
    };

    startAutoSave();

    return () => {
      if (autoSaveTimer.current) {
        clearInterval(autoSaveTimer.current);
      }
    };
  }, [patientId, saveDraftToBackend]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      if (autoSaveTimer.current) {
        clearInterval(autoSaveTimer.current);
      }
    };
  }, []);

  // Get draft data
  const getDraft = useCallback(async () => {
    if (!patientId) return null;

    try {
      const endpoint = encounterId
        ? `/patients/${patientId}/encounters/${encounterId}/draft`
        : `/patients/${patientId}/encounters/draft`;

      const response = await api.get<{ data: EncounterDraft }>(endpoint);
      return response?.data || null;
    } catch {
      return null;
    }
  }, [patientId, encounterId, api]);

  // Delete draft
  const deleteDraft = useCallback(async () => {
    if (!patientId) return;

    try {
      const endpoint = encounterId
        ? `/patients/${patientId}/encounters/${encounterId}/draft`
        : `/patients/${patientId}/encounters/draft`;

      await api.delete(endpoint);
      setDraft(null);
      setLastSavedAt(null);
      pendingData.current = null;
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Failed to delete draft");
      setError(error);
      console.error("Delete draft failed:", error);
    }
  }, [patientId, encounterId, api]);

  // Clear draft locally (without deleting from server)
  const clearDraft = useCallback(() => {
    setDraft(null);
    setLastSavedAt(null);
    pendingData.current = null;

    // Clear debounce timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
  }, []);

  // Format last saved time as "HH:MM AM/PM"
  const getFormattedLastSavedTime = () => {
    if (!lastSavedAt) return null;

    return lastSavedAt.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return {
    draft,
    isSaving,
    lastSavedAt,
    error,
    updateDraft,
    getDraft,
    deleteDraft,
    clearDraft,
    getFormattedLastSavedTime,
  };
}
