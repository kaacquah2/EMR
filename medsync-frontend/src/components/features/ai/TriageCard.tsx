/**
 * Triage Card
 * 
 * Displays patient triage level and urgency assessment.
 */

'use client';

import React from 'react';
import { AlertTriangle, Activity } from 'lucide-react';

interface TriageCardProps {
  triageLevel: 'critical' | 'high' | 'medium' | 'low';
  triageScore: number;
  esiLevel: number;
  recommendedAction: string;
  indicators: Array<{ indicator: string; severity: string }>;
  isLoading?: boolean;
}

export function TriageCard({
  triageLevel,
  triageScore,
  esiLevel,
  recommendedAction,
  indicators = [],
  isLoading = false,
}: TriageCardProps) {
  const getTriageColor = (level: string): { bg: string; border: string; text: string; icon: string } => {
    switch (level) {
      case 'critical':
        return {
          bg: 'bg-red-100',
          border: 'border-red-300 border-2',
          text: 'text-red-900',
          icon: 'text-red-600',
        };
      case 'high':
        return {
          bg: 'bg-orange-100',
          border: 'border-orange-300 border-2',
          text: 'text-orange-900',
          icon: 'text-orange-600',
        };
      case 'medium':
        return {
          bg: 'bg-yellow-100',
          border: 'border-yellow-300 border-2',
          text: 'text-yellow-900',
          icon: 'text-yellow-600',
        };
      default:
        return {
          bg: 'bg-green-100',
          border: 'border-green-300 border-2',
          text: 'text-green-900',
          icon: 'text-green-600',
        };
    }
  };

  const colors = getTriageColor(triageLevel);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-3/4"></div>
          <div className="h-4 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg ${colors.border} ${colors.bg} p-6 space-y-4`}>
      <div className="flex items-center gap-4">
        <AlertTriangle className={`w-8 h-8 ${colors.icon}`} />
        <div>
          <h3 className={`text-2xl font-bold ${colors.text}`}>
            {triageLevel.toUpperCase()}
          </h3>
          <p className={`text-sm ${colors.text}`}>ESI Level {esiLevel}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm text-gray-600 mb-1">Triage Score</p>
          <p className={`text-3xl font-bold ${colors.text}`}>{triageScore.toFixed(0)}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600 mb-1">Emergency Severity Index</p>
          <p className={`text-3xl font-bold ${colors.text}`}>{esiLevel}</p>
        </div>
      </div>

      {recommendedAction && (
        <div className="bg-white bg-opacity-70 rounded p-3">
          <p className="text-sm font-semibold text-gray-900 mb-1">Action:</p>
          <p className="text-sm text-gray-800">{recommendedAction}</p>
        </div>
      )}

      {indicators.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-gray-900 mb-2">Indicators:</p>
          <ul className="space-y-1">
            {indicators.slice(0, 3).map((ind, idx) => (
              <li key={idx} className="text-sm text-gray-800 flex gap-2">
                <Activity className="w-4 h-4 flex-shrink-0" />
                <span>{ind.indicator}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
