/**
 * useCdsAlerts: React hook for managing CDS alerts
 *
 * Handles fetching, acknowledging, and managing clinical decision support alerts.
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useApi } from './use-api';

export interface CdsAlert {
  id: string;
  rule_id: string;
  rule_name: string;
  encounter_id: string;
  severity: 'critical' | 'warning' | 'info';
  message: string;
  context_data?: Record<string, unknown>;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
}

export interface UseCdsAlertsReturn {
  alerts: CdsAlert[];
  loading: boolean;
  error: string | null;
  fetchAlerts: (encounterId: string) => Promise<void>;
  acknowledgeAlert: (alertId: string, notes?: string) => Promise<void>;
  clearError: () => void;
  unacknowledgedCount: number;
  criticalCount: number;
  warningCount: number;
}

/**
 * Hook for managing CDS alerts
 */
export function useCdsAlerts(): UseCdsAlertsReturn {
  const api = useApi();
  const [alerts, setAlerts] = useState<CdsAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async (encounterId: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.get<{ data?: { alerts?: CdsAlert[] }; alerts?: CdsAlert[] }>(
        `/encounters/${encounterId}/cds-alerts`
      );
      setAlerts(response.data?.alerts || response.alerts || []);
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } }; message?: string })?.response?.data?.error ||
        (err as { message?: string })?.message ||
        'Failed to fetch CDS alerts';
      setError(message);
      console.error('Error fetching CDS alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  const acknowledgeAlert = useCallback(async (alertId: string, notes = '') => {
    try {
      const response = await api.post<{ data?: CdsAlert } & CdsAlert>(
        `/cds-alerts/${alertId}/acknowledge`,
        { notes }
      );
      const updatedAlert = response.data || response;
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId ? updatedAlert : alert
        )
      );
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } }; message?: string })?.response?.data?.error ||
        (err as { message?: string })?.message ||
        'Failed to acknowledge alert';
      setError(message);
      console.error('Error acknowledging alert:', err);
      throw err;
    }
  }, [api]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Count unacknowledged alerts
  const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;
  const criticalCount = alerts.filter(
    (a) => a.severity === 'critical' && !a.acknowledged
  ).length;
  const warningCount = alerts.filter(
    (a) => a.severity === 'warning' && !a.acknowledged
  ).length;

  return {
    alerts,
    loading,
    error,
    fetchAlerts,
    acknowledgeAlert,
    clearError,
    unacknowledgedCount,
    criticalCount,
    warningCount,
  };
}

/**
 * Hook for auto-fetching alerts on encounter change
 */
export function useCdsAlertsForEncounter(encounterId?: string) {
  const { alerts, loading, error, fetchAlerts, acknowledgeAlert, clearError } =
    useCdsAlerts();

  useEffect(() => {
    if (encounterId) {
      fetchAlerts(encounterId);
    }
  }, [encounterId, fetchAlerts]);

  return {
    alerts,
    loading,
    error,
    acknowledgeAlert,
    clearError,
    unacknowledgedCount: alerts.filter((a) => !a.acknowledged).length,
    criticalCount: alerts.filter(
      (a) => a.severity === 'critical' && !a.acknowledged
    ).length,
    warningCount: alerts.filter(
      (a) => a.severity === 'warning' && !a.acknowledged
    ).length,
  };
}

export default useCdsAlerts;
