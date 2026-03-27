/**
 * Similar Patients
 *
 * Displays similar patient cases for treatment benchmarking.
 */

'use client';

import React from 'react';
import { Users, FileText } from 'lucide-react';

interface SimilarPatient {
  patient_id: string;
  similarity_score: number;
  conditions: string[];
  treatment_outcome?: string;
  success_rate?: number;
}

interface SimilarPatientsProps {
  similarPatients: SimilarPatient[];
  isLoading?: boolean;
}

export function SimilarPatients({
  similarPatients,
  isLoading = false,
}: SimilarPatientsProps) {
  if (isLoading) {
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

  if (!similarPatients || similarPatients.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <Users className="w-5 h-5 text-gray-500" />
          Similar Patients
        </h3>
        <p className="text-sm text-gray-600">
          No similar cases found. Similarity search may require more indexed patient data.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Users className="w-5 h-5 text-gray-500" />
        Similar Patients ({similarPatients.length})
      </h3>
      <div className="space-y-3">
        {similarPatients.map((p, idx) => (
          <div
            key={p.patient_id || idx}
            className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
          >
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <span className="font-mono text-sm text-gray-600">
                  {String(p.patient_id).slice(0, 8)}...
                </span>
              </div>
              <span className="text-sm font-semibold text-blue-600">
                {(p.similarity_score * 100).toFixed(0)}% match
              </span>
            </div>
            {p.conditions && p.conditions.length > 0 && (
              <p className="text-sm text-gray-700 mt-2">
                Conditions: {p.conditions.join(', ')}
              </p>
            )}
            {p.treatment_outcome && (
              <p className="text-sm text-gray-600 mt-1">Outcome: {p.treatment_outcome}</p>
            )}
            {p.success_rate != null && (
              <p className="text-xs text-gray-500 mt-1">
                Success rate: {(p.success_rate * 100).toFixed(0)}%
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
