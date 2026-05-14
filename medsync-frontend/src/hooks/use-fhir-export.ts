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

/**
 * Hook for exporting patient FHIR data
 * @param patientId - UUID of patient to export
 * @returns Object with export state and trigger function
 */
export function useFhirExport(patientId: string) {
  useApi();
  const [state, setState] = useState<FhirExportState>({
    loading: false,
    error: null,
    consentScope: null,
    progress: 0,
  });

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
        // Call GET /fhir/Patient/{id}/$everything
        const response = await fetch(
          `/api/v1/fhir/Patient/${patientId}/$everything`,
          {
            method: 'GET',
            headers: {
              Accept: 'application/fhir+json',
              'Content-Type': 'application/fhir+json',
            },
            credentials: 'include',
          }
        );

        setState((prev) => ({ ...prev, progress: 50 }));

        if (!response.ok) {
          let errorMsg = `Export failed (${response.status})`;

          try {
            const errorData = await response.json();
            if (errorData.issue?.[0]?.diagnostics) {
              errorMsg = errorData.issue[0].diagnostics;
            }
          } catch {
            // Fallback to status text
            errorMsg = response.statusText || errorMsg;
          }

          setState((prev) => ({
            ...prev,
            error: errorMsg,
            loading: false,
            progress: 0,
          }));
          options?.onError?.(errorMsg);
          return;
        }

        const bundle = await response.json();

        setState((prev) => ({ ...prev, progress: 80 }));

        // Extract consent scope from metadata if available
        const scope = bundle.meta?.extension?.find(
          (ext: { url: string }) =>
            ext.url === 'http://medsync.org/fhir/consent-scope'
        )?.valueString as 'SUMMARY' | 'FULL_RECORD' | undefined;

        // Generate filename with timestamp
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `patient-${patientId}-bundle-${timestamp}.json`;

        // Create blob and trigger download
        const blob = new Blob([JSON.stringify(bundle, null, 2)], {
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
    [patientId]
  );

  /**
   * Export individual resource (not full $everything)
   * @param resourceType - FHIR resource type (Patient, Encounter, etc.)
   * @param resourceId - Resource UUID
   */
  const exportResource = useCallback(
    async (
      resourceType: 'Patient' | 'Encounter' | 'Condition' | 'MedicationRequest' | 'Observation' | 'DiagnosticReport',
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
        const response = await fetch(`/api/v1/fhir/${resourceType}/${resourceId}`, {
          method: 'GET',
          headers: {
            Accept: 'application/fhir+json',
            'Content-Type': 'application/fhir+json',
          },
          credentials: 'include',
        });

        setState((prev) => ({ ...prev, progress: 50 }));

        if (!response.ok) {
          const errorMsg = `Failed to export ${resourceType} (${response.status})`;
          setState((prev) => ({
            ...prev,
            error: errorMsg,
            loading: false,
            progress: 0,
          }));
          options?.onError?.(errorMsg);
          return;
        }

        const resource = await response.json();
        setState((prev) => ({ ...prev, progress: 80 }));

        // Generate filename
        const timestamp = new Date().toISOString().split('T')[0];
        const filename = `${resourceType.toLowerCase()}-${resourceId}-${timestamp}.json`;

        // Download
        const blob = new Blob([JSON.stringify(resource, null, 2)], {
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
    []
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
