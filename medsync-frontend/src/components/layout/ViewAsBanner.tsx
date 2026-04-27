'use client';

import React from 'react';
import { useAuth } from '@/lib/auth-context';
import { X } from 'lucide-react';

/**
 * ViewAsBanner: Persistent teal banner at top of page when super_admin is viewing as a hospital.
 * 
 * Displays: "Viewing as: [Hospital Name] — all actions scoped [×]"
 * Click [×] to clear view-as state and return to viewing all hospitals.
 * 
 * Only visible when user.role === 'super_admin' AND viewAsHospitalId is set.
 */
export function ViewAsBanner() {
  const { user, viewAsHospitalId, viewAsHospitalName, setViewAs } = useAuth();

  // Only show for super_admin with active view-as
  if (user?.role !== 'super_admin' || !viewAsHospitalId) {
    return null;
  }

  const handleClear = () => {
    setViewAs(null, null);
  };

  return (
    <div className="bg-[#0B8A96] text-white px-6 py-3 flex items-center justify-between">
      <div className="text-sm font-medium">
        Viewing as: <span className="font-semibold">{viewAsHospitalName || 'Unknown Hospital'}</span> — all actions scoped to this hospital
      </div>
      <button
        onClick={handleClear}
        className="text-white hover:opacity-80 transition-opacity"
        aria-label="Clear view-as selection"
        title="Return to viewing all hospitals"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}
