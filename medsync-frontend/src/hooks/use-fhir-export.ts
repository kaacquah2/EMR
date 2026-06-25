"use client";

/**
 * useFhirExport Hook
 *
 * Provides functionality to export patient data as FHIR R4 Bundle.
 * Handles:
 * - Triggering $everything operation endpoint
 * - Downloading Bundle as JSON file
 * - Error handling and user feedback
 * - Tracking consent scope (SUMMARY vs FULL_RECORD)
 */

import { useState, useCallback } from 'react';
import { useApi } from './use-api';

interface FhirExportState {
  loading: boolean;
  error: string | null;
  consentScope: 'SUMMARY' | 'FULL_RECORD' | null;
  progress: number; // 0-100
}

interface FhirExportOptions {
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

type FhirResourceType =
  | 'Patient'
  | 'Encounter'
  | 'Condition'
  | 'MedicationRequest'
  | 'Observation'
  | 'DiagnosticReport';

/**
 * Hook for exporting patient FHIR data
 * @param patientId - UUID of patient to export
 * @returns Object with export state and trigger function
 */
export function useFhirExport(patientId: string) {
  const api = useApi();

  const [state, setState] = useState<FhirExportState>({
    loading: false,
    error: null,
    consentScope: null,
    progress: 0,
  });

  /** Trigger a file download from a JS object. */
  function downloadJson(data: unknown, filename: string) {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/fhir+json',
    });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(downloadUrl);
  }

  /**
   * Trigger FHIR $everything export and download as JSON
   */
  const exportFhirBundle = useCallback(
    async (options?: FhirExportOptions) => {
      if (!patientId) {
        const error = 'Patient ID is required';
        setState((prev) => ({ ...prev, error, loading: false }));
        options?.onError?.(error);
        return;
      }

      setState((prev) => ({
        ...prev,
        loading: true,
        error: null,
        progress: 10,
      }));

      try {
        // Call GET /fhir/Patient/{id}/$everything via the shared API client.
        // API_BASE already includes /api/v1, so the path is relative to that.
        // The client injects Authorization: Bearer automatically.
        const bundle = await api.get<Record<string, unknown>>(
          `/fhir/Patient/${patientId}/$everything`
        );

        setState((prev) => ({ ...prev, progress: 50 }));

        // Extract consent scope from metadata if available
        const scope = (
          bundle.meta as
            | { extension?: Array<{ url: string; valueString?: string }> }
            | undefined
        )?.extension?.find(
          (ext) => ext.url === 'http://medsync.org/fhir/consent-scope'
        )?.valueString as 'SUMMARY' | 'FULL_RECORD' | undefined;

        setState((prev) => ({ ...prev, progress: 80 }));

        // Generate filename with timestamp
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `patient-${patientId}-bundle-${timestamp}.json`;

        downloadJson(bundle, filename);

        setState((prev) => ({
          ...prev,
          loading: false,
          error: null,
          consentScope: scope || 'FULL_RECORD',
          progress: 100,
        }));

        options?.onSuccess?.();

        // Reset progress after short delay
        setTimeout(() => {
          setState((prev) => ({ ...prev, progress: 0 }));
        }, 2000);
      } catch (err) {
        const error =
          err instanceof Error ? err.message : 'Failed to export FHIR bundle';

        setState((prev) => ({
          ...prev,
          error,
          loading: false,
          progress: 0,
        }));
        options?.onError?.(error);
      }
    },
    [api, patientId]
  );

  /**
   * Export individual resource (not full $everything)
   * @param resourceType - FHIR resource type (Patient, Encounter, etc.)
   * @param resourceId - Resource UUID
   */
  const exportResource = useCallback(
    async (
      resourceType: FhirResourceType,
      resourceId: string,
      options?: FhirExportOptions
    ) => {
      setState((prev) => ({
        ...prev,
        loading: true,
        error: null,
        progress: 10,
      }));

      try {
        // Route through shared API client (Bearer token + API_BASE).
        const resource = await api.get<Record<string, unknown>>(
          `/fhir/${resourceType}/${resourceId}`
        );

        setState((prev) => ({ ...prev, progress: 80 }));

        // Generate filename
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `${resourceType.toLowerCase()}-${resourceId}-${timestamp}.json`;

        downloadJson(resource, filename);

        setState((prev) => ({
          ...prev,
          loading: false,
          error: null,
          progress: 100,
        }));

        options?.onSuccess?.();

        setTimeout(() => {
          setState((prev) => ({ ...prev, progress: 0 }));
        }, 2000);
      } catch (err) {
        const error = err instanceof Error ? err.message : 'Export failed';
        setState((prev) => ({
          ...prev,
          error,
          loading: false,
          progress: 0,
        }));
        options?.onError?.(error);
      }
    },
    [api]
  );

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    exportFhirBundle,
    exportResource,
    clearError,
  };
}
