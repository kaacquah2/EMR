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
    <div className="relative overflow-hidden bg-gradient-to-r from-indigo-700 via-indigo-600 to-indigo-700 text-white px-6 py-3 flex items-center justify-between shadow-xl border-b border-white/20">
      {/* Decorative pulse effect background */}
      <div className="absolute inset-0 bg-white/5 animate-pulse pointer-events-none" />
      
      <div className="flex items-center gap-4 relative z-10">
        <div className="flex items-center gap-2">
          <div className="relative">
            <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-75" />
            <span className="relative flex h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          </div>
          <span className="text-[11px] font-bold tracking-widest uppercase bg-white/25 backdrop-blur-sm px-2 py-1 rounded shadow-inner border border-white/10">
            Super Admin Mode
          </span>
        </div>
        <div className="text-[15px] font-medium tracking-tight">
          Viewing as: <span className="font-bold underline decoration-white/60 underline-offset-4 decoration-2">{viewAsHospitalName || 'Unknown Hospital'}</span>
          <span className="ml-3 text-white/90 hidden sm:inline font-normal border-l border-white/20 pl-3">All clinical actions are scoped to this facility</span>
        </div>
      </div>
      
      <button
        onClick={handleClear}
        className="relative z-10 flex items-center gap-2 bg-white/15 hover:bg-white/25 active:scale-95 px-4 py-1.5 rounded-lg text-xs font-bold transition-all group border border-white/10 hover:border-white/30 shadow-sm"
        aria-label="Exit view-as mode"
      >
        <span>Exit Session</span>
        <X className="w-4 h-4 group-hover:rotate-90 transition-transform" />
      </button>
    </div>
  );
}
