/**
 * AI Alerts Panel
 * 
 * Displays clinical alerts and warnings from AI analysis.
 */

'use client';

import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react';

interface AIAlertsPanelProps {
  alerts: string[];
  recommendedActions: string[];
  isLoading?: boolean;
}

export function AIAlertsPanel({
  alerts = [],
  recommendedActions = [],
  isLoading = false,
}: AIAlertsPanelProps) {
  const getAlertLevel = (alert: string): 'critical' | 'warning' | 'info' => {
    if (alert.includes('CRITICAL') || alert.includes('URGENT')) return 'critical';
    if (alert.includes('⚠️')) return 'warning';
    return 'info';
  };

  const getAlertIcon = (level: 'critical' | 'warning' | 'info') => {
    switch (level) {
      case 'critical':
        return <AlertTriangle className="w-5 h-5 text-red-600" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-orange-600" />;
      default:
        return <CheckCircle2 className="w-5 h-5 text-blue-600" />;
    }
  };

  const getAlertColor = (level: 'critical' | 'warning' | 'info'): string => {
    switch (level) {
      case 'critical':
        return 'bg-red-50 border-red-200 border-l-4 border-l-red-600';
      case 'warning':
        return 'bg-orange-50 border-orange-200 border-l-4 border-l-orange-600';
      default:
        return 'bg-blue-50 border-blue-200 border-l-4 border-l-blue-600';
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">AI Alerts & Recommendations</h3>

      {alerts.length === 0 && recommendedActions.length === 0 ? (
        <p className="text-sm text-gray-600 text-center py-4">No alerts or recommendations</p>
      ) : (
        <>
          {/* Alerts */}
          {alerts.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-gray-900">Alerts</h4>
              {alerts.map((alert, idx) => {
                const level = getAlertLevel(alert);
                return (
                  <div key={idx} className={`rounded p-3 flex gap-3 ${getAlertColor(level)}`}>
                    {getAlertIcon(level)}
                    <p className="text-sm text-gray-800">{alert}</p>
                  </div>
                );
              })}
            </div>
          )}

          {/* Recommended Actions */}
          {recommendedActions.length > 0 && (
            <div className="border-t pt-4 space-y-2">
              <h4 className="text-sm font-semibold text-gray-900">Recommended Actions</h4>
              <ul className="space-y-2">
                {recommendedActions.map((action, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-gray-700">
                    <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
