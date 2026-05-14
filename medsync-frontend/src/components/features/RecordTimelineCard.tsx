import React from "react";
import type { MedicalRecord } from "@/lib/types";
import { Button } from "@/components/ui/button";

const TYPE_COLORS: Record<string, string> = {
  diagnosis: "#1D6FA4",
  prescription: "#6D28D9",
  lab_result: "#D97706",
  vital_signs: "#059669",
  allergy: "#DC2626",
  nursing_note: "#64748B",
};

interface RecordTimelineCardProps {
  record: MedicalRecord;
  hospitalName?: string;
  onAmend?: (record: MedicalRecord) => void;
  canAmend?: boolean;
}

export function RecordTimelineCard({ record, hospitalName, onAmend, canAmend }: RecordTimelineCardProps) {
  const color = TYPE_COLORS[record.record_type] || "#64748B";

  return (
    <div
      className="rounded-xl border-l-4 bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
      style={{ borderLeftColor: color }}
    >
      <div className="flex justify-between gap-4">
        <div className="flex-1">
          <span className="font-mono text-xs text-slate-500 dark:text-slate-500">
            {new Date(record.created_at).toLocaleString()}
          </span>
          {hospitalName && (
            <span className="ml-2 rounded-full bg-slate-100 dark:bg-slate-900 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-500">
              Recorded at {hospitalName}
            </span>
          )}
          {record.is_amended && (
            <span className="ml-2 rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs text-[#B45309]">Amended</span>
          )}
        </div>
        {canAmend && onAmend && (
          <Button type="button" variant="secondary" size="sm" onClick={() => onAmend(record)}>
            Amend
          </Button>
        )}
      </div>
      <div className="mt-2">
        {record.diagnosis && (
          <p className="font-medium">
            {record.diagnosis.icd10_code} — {record.diagnosis.icd10_description}
          </p>
        )}
        {record.prescription && (
          <p className="font-medium">
            {record.prescription.drug_name} {record.prescription.dosage}
          </p>
        )}
        {record.lab_result && (
          <p className="font-medium">
            {record.lab_result.test_name}: {record.lab_result.result_value}
          </p>
        )}
        {record.vital && (
          <p className="font-medium">
            Vitals recorded
          </p>
        )}
        {record.record_type === "allergy" && (
          <p className="font-medium">Allergy recorded</p>
        )}
        {record.record_type === "nursing_note" && (
          <p className="font-medium">Nursing note</p>
        )}
      </div>
      {record.amendment_reason && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-500">Amendment reason: {record.amendment_reason}</p>
      )}
    </div>
  );
}
