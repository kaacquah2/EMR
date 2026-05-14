/**
 * Clinical Decision Support (CDS) Alerts Panel
 *
 * Displays inline alerts when creating prescriptions/diagnoses.
 * Color-coded by severity: red (critical), amber (warning), blue (info).
 * Allows doctors to acknowledge alerts before saving.
 */

'use client';

import React, { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, Check } from 'lucide-react';

export interface CdsAlertData {
  id: string;
  rule_id: string;
  rule_name: string;
  severity: 'critical' | 'warning' | 'info';
  message: string;
  context_data?: Record<string, unknown>;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
}

interface CdsAlertsPanelProps {
  alerts: CdsAlertData[];
  onAcknowledge?: (alertId: string, notes?: string) => Promise<void>;
  loading?: boolean;
  compact?: boolean;
}

/**
 * Color and icon mapping for severity levels
 */
const SEVERITY_CONFIG = {
  critical: {
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-200 dark:border-red-800',
    textColor: 'text-red-900 dark:text-red-100',
    badgeColor: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100',
    icon: AlertTriangle,
    label: 'Critical',
  },
  warning: {
    bgColor: 'bg-amber-50 dark:bg-amber-950/30',
    borderColor: 'border-amber-200 dark:border-amber-800',
    textColor: 'text-amber-900 dark:text-amber-100',
    badgeColor: 'bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100',
    icon: AlertCircle,
    label: 'Warning',
  },
  info: {
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
    borderColor: 'border-blue-200 dark:border-blue-800',
    textColor: 'text-blue-900 dark:text-blue-100',
    badgeColor: 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100',
    icon: Info,
    label: 'Information',
  },
};

/**
 * Single alert card with acknowledgment button
 */
function CdsAlertCard({
  alert,
  onAcknowledge,
  loading,
}: {
  alert: CdsAlertData;
  onAcknowledge?: (alertId: string) => Promise<void>;
  loading?: boolean;
}) {
  const [isAcknowledging, setIsAcknowledging] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [notes, setNotes] = useState('');

  const config = SEVERITY_CONFIG[alert.severity];
  const IconComponent = config.icon;

  const handleAcknowledge = async () => {
    if (!onAcknowledge) return;

    setIsAcknowledging(true);
    try {
      await onAcknowledge(alert.id);
      setNotes('');
      setShowNotes(false);
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    } finally {
      setIsAcknowledging(false);
    }
  };

  return (
    <div
      className={`rounded-lg border-l-4 p-4 ${config.bgColor} ${config.borderColor}`}
    >
      <div className="flex items-start gap-3">
        <IconComponent className={`h-5 w-5 flex-shrink-0 ${config.textColor}`} />

        <div className="flex-grow">
          <div className="flex items-center gap-2">
            <h4 className={`font-semibold ${config.textColor}`}>
              {alert.rule_name}
            </h4>
            <span
              className={`inline-block rounded px-2 py-1 text-xs font-medium ${config.badgeColor}`}
            >
              {config.label}
            </span>
          </div>

          <p className={`mt-1 text-sm ${config.textColor}`}>{alert.message}</p>

          {/* Context details */}
          {alert.context_data && Object.keys(alert.context_data).length > 0 && (
            <div className={`mt-2 space-y-1 text-xs ${config.textColor} opacity-75`}>
              {Object.entries(alert.context_data).map(([key, value]) => (
                <div key={key}>
                  <strong>{key}:</strong> {String(value)}
                </div>
              ))}
            </div>
          )}

          {alert.acknowledged && (
            <div className="mt-2 flex items-center gap-2 text-xs text-green-600 dark:text-green-400">
              <Check className="h-4 w-4" />
              <span>
                Acknowledged{alert.acknowledged_by ? ` by ${alert.acknowledged_by}` : ''}{' '}
                {alert.acknowledged_at
                  ? new Date(alert.acknowledged_at).toLocaleString()
                  : ''}
              </span>
            </div>
          )}
        </div>

        {!alert.acknowledged && onAcknowledge && (
          <div className="flex flex-shrink-0 gap-2">
            <button
              onClick={() => setShowNotes(!showNotes)}
              disabled={isAcknowledging || loading}
              className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
                config.textColor
              } hover:opacity-80 disabled:opacity-50`}
            >
              Acknowledge
            </button>
          </div>
        )}
      </div>

      {/* Notes input */}
      {showNotes && !alert.acknowledged && (
        <div className="mt-3 border-t border-current border-opacity-20 pt-3">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add acknowledgment notes (optional)..."
            className={`w-full rounded border p-2 text-sm ${config.borderColor}`}
            rows={2}
            disabled={isAcknowledging || loading}
          />
          <div className="mt-2 flex justify-end gap-2">
            <button
              onClick={() => setShowNotes(false)}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                config.textColor
              } hover:opacity-80`}
              disabled={isAcknowledging || loading}
            >
              Cancel
            </button>
            <button
              onClick={handleAcknowledge}
              disabled={isAcknowledging || loading}
              className={`flex items-center gap-2 px-3 py-1 text-sm font-medium rounded text-white transition-colors ${
                config.badgeColor.split(' ')[0] === 'bg-red-100'
                  ? 'bg-red-600 hover:bg-red-700'
                  : config.badgeColor.split(' ')[0] === 'bg-amber-100'
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-blue-600 hover:bg-blue-700'
              } disabled:opacity-50`}
            >
              {isAcknowledging ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" />
                  Acknowledge
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * CDS Alerts Panel - Main component
 *
 * Displays alerts grouped by severity with color coding.
 */
export function CdsAlertsPanel({
  alerts,
  onAcknowledge,
  loading = false,
  compact = false,
}: CdsAlertsPanelProps) {
  if (!alerts || alerts.length === 0) {
    return null;
  }

  // Group alerts by severity
  const criticalAlerts = alerts.filter((a) => a.severity === 'critical');
  const warningAlerts = alerts.filter((a) => a.severity === 'warning');
  const infoAlerts = alerts.filter((a) => a.severity === 'info');

  // Filter out acknowledged alerts if in compact mode
  const unacknowledgedCritical = criticalAlerts.filter((a) => !a.acknowledged);
  const unacknowledgedWarning = warningAlerts.filter((a) => !a.acknowledged);
  const unacknowledgedInfo = infoAlerts.filter((a) => !a.acknowledged);

  const totalUnacknowledged =
    unacknowledgedCritical.length +
    unacknowledgedWarning.length +
    unacknowledgedInfo.length;

  if (compact && totalUnacknowledged === 0) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Critical Alerts */}
      {unacknowledgedCritical.length > 0 && (
        <div className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-400">
            <AlertTriangle className="h-4 w-4" />
            Critical Alerts ({unacknowledgedCritical.length})
          </h3>
          <div className="space-y-2">
            {unacknowledgedCritical.map((alert) => (
              <CdsAlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={onAcknowledge}
                loading={loading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Warning Alerts */}
      {unacknowledgedWarning.length > 0 && (
        <div className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
            <AlertCircle className="h-4 w-4" />
            Warnings ({unacknowledgedWarning.length})
          </h3>
          <div className="space-y-2">
            {unacknowledgedWarning.map((alert) => (
              <CdsAlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={onAcknowledge}
                loading={loading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Info Alerts */}
      {unacknowledgedInfo.length > 0 && (
        <div className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-blue-700 dark:text-blue-400">
            <Info className="h-4 w-4" />
            Information ({unacknowledgedInfo.length})
          </h3>
          <div className="space-y-2">
            {unacknowledgedInfo.map((alert) => (
              <CdsAlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={onAcknowledge}
                loading={loading}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CdsAlertsPanel;
