/**
 * Referral Suggestions
 *
 * Displays recommended hospitals for inter-hospital referral.
 */

'use client';

import React from 'react';
import { Building2, MapPin, Bed } from 'lucide-react';

interface RecommendedHospital {
  hospital_name: string;
  hospital_id: string;
  specialty_match: number;
  bed_availability: number;
  distance_km?: number;
  reason: string;
}

interface ReferralSuggestionsProps {
  recommendedHospitals: RecommendedHospital[];
  isLoading?: boolean;
}

export function ReferralSuggestions({
  recommendedHospitals,
  isLoading = false,
}: ReferralSuggestionsProps) {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!recommendedHospitals || recommendedHospitals.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <Building2 className="w-5 h-5 text-gray-500" />
          Referral Recommendations
        </h3>
        <p className="text-sm text-gray-600">
          No referral recommendations at this time. Use the referral recommendation endpoint with a specialty for suggestions.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Building2 className="w-5 h-5 text-gray-500" />
        Recommended Hospitals ({recommendedHospitals.length})
      </h3>
      <div className="space-y-4">
        {recommendedHospitals.map((h, idx) => (
          <div
            key={h.hospital_id || idx}
            className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
          >
            <div className="flex justify-between items-start">
              <h4 className="font-semibold text-gray-900">{h.hospital_name}</h4>
              <span className="text-sm font-medium text-blue-600">
                {(h.specialty_match * 100).toFixed(0)}% specialty match
              </span>
            </div>
            <div className="flex flex-wrap gap-3 mt-2 text-sm text-gray-600">
              <span className="flex items-center gap-1">
                <Bed className="w-4 h-4" />
                {h.bed_availability} beds
              </span>
              {h.distance_km != null && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-4 h-4" />
                  {h.distance_km} km
                </span>
              )}
            </div>
            <p className="text-sm text-gray-700 mt-2">{h.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
