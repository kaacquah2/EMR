/**
 * Analysis History
 *
 * Timeline of past AI analyses for the patient.
 */

'use client';

import React from 'react';
import { History, FileText } from 'lucide-react';
import type { AnalysisHistoryItem } from '@/hooks/use-ai-analysis';

interface AnalysisHistoryProps {
  analyses: AnalysisHistoryItem[];
  total: number;
  isLoading?: boolean;
  onLoadMore?: () => void;
  hasMore?: boolean;
}

export function AnalysisHistory({
  analyses,
  total,
  isLoading = false,
  onLoadMore,
  hasMore = false,
}: AnalysisHistoryProps) {
  if (isLoading && analyses.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!analyses || analyses.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <History className="w-5 h-5 text-gray-500" />
          Analysis History
        </h3>
        <p className="text-sm text-gray-600">
          No past analyses yet. Run a comprehensive analysis to see history here.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <History className="w-5 h-5 text-gray-500" />
        Analysis History ({total})
      </h3>
      <ul className="space-y-3">
        {analyses.map((a) => (
          <li
            key={a.id}
            className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 flex gap-3"
          >
            <FileText className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between items-start gap-2">
                <span className="font-medium text-gray-900 capitalize">
                  {a.analysis_type.replace(/_/g, ' ')}
                </span>
                <time className="text-xs text-gray-500 flex-shrink-0">
                  {a.created_at ? new Date(a.created_at).toLocaleString() : '—'}
                </time>
              </div>
              {a.agents_executed && a.agents_executed.length > 0 && (
                <p className="text-xs text-gray-600 mt-1">
                  Agents: {a.agents_executed.join(', ')}
                </p>
              )}
              {a.clinical_summary && (
                <p className="text-sm text-gray-700 mt-2 line-clamp-2">
                  {a.clinical_summary}
                </p>
              )}
              {a.alerts && a.alerts.length > 0 && (
                <p className="text-xs text-amber-700 mt-1">
                  {a.alerts.length} alert(s)
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
      {hasMore && onLoadMore && (
        <button
          type="button"
          onClick={onLoadMore}
          className="mt-4 w-full py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg border border-blue-200"
        >
          Load more
        </button>
      )}
    </div>
  );
}
