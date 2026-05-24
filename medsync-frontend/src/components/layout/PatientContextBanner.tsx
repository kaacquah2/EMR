"use client";

import React from "react";
import { AlertCircle, Droplets, Info } from "lucide-react";
import Image from "next/image";
import { Badge } from "@/components/ui/badge";

interface Allergy {
  id: string;
  allergen: string;
  severity: string;
}

interface ClinicalAlert {
  id: string;
  severity: string;
  message: string;
}

interface PatientContextBannerProps {
  patient: {
    id: string;
    full_name: string;
    age: number;
    gender: string;
    ghana_health_id: string;
    blood_group: string;
    admission_status?: "admitted" | "outpatient" | "emergency";
    ward_name?: string;
    bed_code?: string;
    photo_url?: string;
  };
  allergies: Allergy[];
  activeAlerts: ClinicalAlert[];
}

/**
 * Persistent Patient Context Banner
 * 
 * Sticky header showing essential patient information to prevent wrong-patient errors.
 */
export function PatientContextBanner({
  patient,
  allergies = [],
  activeAlerts = [],
}: PatientContextBannerProps) {
  const initials = patient.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase();

  return (
    <div className="sticky top-0 z-40 w-full bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm transition-all duration-200">
      <div className="container mx-auto px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Patient Identity Section */}
          <div className="flex items-center gap-4">
            <div className="flex-shrink-0">
              {patient.photo_url ? (
                <Image
                  src={patient.photo_url}
                  alt={patient.full_name}
                  width={48}
                  height={48}
                  className="h-12 w-12 rounded-full object-cover border-2 border-slate-100"
                />
              ) : (
                <div className="h-12 w-12 rounded-full bg-indigo-100 dark:bg-indigo-950 flex items-center justify-center text-indigo-700 dark:text-indigo-300 font-bold text-lg border-2 border-indigo-200 dark:border-indigo-800">
                  {initials}
                </div>
              )}
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white leading-tight">
                  {patient.full_name}
                </h2>
                <Badge variant={patient.admission_status === "admitted" ? "success" : "secondary"} className="text-[10px] uppercase tracking-wider">
                  {patient.admission_status || "Outpatient"}
                </Badge>
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
                <span>{patient.age}y · {patient.gender}</span>
                <span className="text-slate-300 dark:text-slate-600">|</span>
                <span className="font-mono text-xs tracking-tight">MRN: {patient.ghana_health_id}</span>
              </div>
            </div>
          </div>

          {/* Clinical Context Section */}
          <div className="flex flex-wrap items-center gap-6">
            {/* Blood Group */}
            <div className="flex flex-col items-center gap-1">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Blood</span>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 font-bold border border-red-100 dark:border-red-900/50">
                <Droplets className="h-3.5 w-3.5" />
                <span>{patient.blood_group}</span>
              </div>
            </div>

            {/* Allergies */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Allergies</span>
              <div className="flex gap-1.5 flex-wrap">
                {allergies.length > 0 ? (
                  allergies.map((allergy) => (
                    <Badge 
                      key={allergy.id} 
                      variant="critical" 
                      className="bg-red-600 text-white hover:bg-red-700 border-none px-2 py-0.5"
                    >
                      {allergy.allergen}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-slate-400 italic">No known allergies</span>
                )}
              </div>
            </div>

            {/* Active Alerts */}
            {activeAlerts.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Active Alerts</span>
                <div className="flex items-center gap-2 px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border border-amber-100 dark:border-amber-900/50 animate-pulse">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm font-semibold">{activeAlerts.length} Clinical Alert(s)</span>
                </div>
              </div>
            )}

            {/* Admission Context */}
            {patient.admission_status === "admitted" && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">Location</span>
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 border border-blue-100 dark:border-blue-900/50">
                  <Info className="h-3.5 w-3.5" />
                  <span className="text-sm font-medium">{patient.ward_name} · Bed {patient.bed_code}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
