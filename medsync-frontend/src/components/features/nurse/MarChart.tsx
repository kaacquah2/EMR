"use client";

import React from "react";
import { Check, AlertCircle, Clock } from "lucide-react";


interface Medication {
  id: string;
  drug_name: string;
  dosage: string;
  frequency: string;
}

interface Dose {
  id: string;
  medication_id: string;
  scheduled_time: string;
  status: "scheduled" | "administered" | "missed" | "held" | "refused";
  administered_at?: string;
  administered_by?: string;
}

interface MarChartProps {
  medications: Medication[];
  doses: Dose[];
  onAdminister: (doseId: string) => Promise<void>;
}

/**
 * Medication Administration Record (MAR)
 * 
 * Grid view of medications and their scheduled doses.
 */
export function MarChart({ medications, doses, onAdminister }: MarChartProps) {
  // Generate time slots for the day (e.g., 24 hours)
  const timeSlots = Array.from({ length: 24 }, (_, i) => i);

  const getDoseAt = (medId: string, hour: number) => {
    return doses.find(d => {
      const date = new Date(d.scheduled_time);
      return d.medication_id === medId && date.getHours() === hour;
    });
  };

  const getStatusColor = (status: Dose["status"]) => {
    switch (status) {
      case "administered": return "bg-green-100 text-green-700 border-green-200 dark:bg-green-950/30 dark:text-green-400 dark:border-green-900/50";
      case "missed": return "bg-red-100 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-400 dark:border-red-900/50";
      case "scheduled": return "bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-800";
      default: return "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900/50";
    }
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-950">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
            <th className="sticky left-0 z-20 bg-slate-50 dark:bg-slate-900 p-4 text-left font-bold text-slate-700 dark:text-slate-300 min-w-[250px] border-r border-slate-200 dark:border-slate-800">
              Medication & Dosage
            </th>
            {timeSlots.map(hour => (
              <th key={hour} className="p-2 text-xs font-medium text-slate-500 dark:text-slate-400 border-r border-slate-100 dark:border-slate-800 min-w-[60px]">
                {hour}:00
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {medications.map((med) => (
            <tr key={med.id} className="border-b border-slate-100 dark:border-slate-900 hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors">
              <td className="sticky left-0 z-10 bg-white dark:bg-slate-950 p-4 border-r border-slate-200 dark:border-slate-800">
                <div className="flex flex-col">
                  <span className="font-bold text-slate-900 dark:text-white">{med.drug_name}</span>
                  <span className="text-sm text-slate-500 dark:text-slate-400">{med.dosage} · {med.frequency}</span>
                </div>
              </td>
              {timeSlots.map(hour => {
                const dose = getDoseAt(med.id, hour);
                const isPast = hour < new Date().getHours();
                const isMissed = dose?.status === "scheduled" && isPast;

                return (
                  <td key={hour} className="p-2 border-r border-slate-50 dark:border-slate-900 text-center">
                    {dose ? (
                      <button
                        onClick={() => dose.status === "scheduled" && onAdminister(dose.id)}
                        disabled={dose.status !== "scheduled"}
                        className={`w-10 h-10 rounded-lg border flex items-center justify-center transition-all ${
                          isMissed ? getStatusColor("missed") : getStatusColor(dose.status)
                        } ${dose.status === "scheduled" ? "hover:scale-105 active:scale-95 cursor-pointer" : "cursor-default"}`}
                        title={dose.status}
                      >
                        {dose.status === "administered" ? (
                          <Check className="h-5 w-5" />
                        ) : isMissed ? (
                          <AlertCircle className="h-5 w-5" />
                        ) : (
                          <Clock className="h-4 w-4 opacity-50" />
                        )}
                      </button>
                    ) : (
                      <div className="w-10 h-10 mx-auto rounded-lg border border-dashed border-slate-100 dark:border-slate-900" />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="p-4 flex flex-wrap gap-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" /> Administered
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" /> Missed
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-slate-300" /> Scheduled
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-amber-500" /> Held / Refused
        </div>
      </div>
    </div>
  );
}
