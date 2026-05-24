/* eslint-disable @next/next/no-img-element */
"use client";

import React from "react";
import { Patient, MedicalRecord, User } from "@/lib/types";

interface PrintableMedicalRecordProps {
  patient: Patient;
  record: MedicalRecord;
  hospitalName: string;
  provider: User;
}

/**
 * Printable Medical Record Component
 * 
 * Uses clinical-print.css styles to format a record for printing.
 * Hidden on screen, shown in print mode.
 */
export function PrintableMedicalRecord({
  patient,
  record,
  hospitalName,
  provider,
}: PrintableMedicalRecordProps) {
  return (
    <div className="print-only hidden p-8 bg-white text-black font-sans">
      {/* Letterhead */}
      <div className="letterhead flex justify-between items-center border-b-2 border-[#0EAFBE] pb-6 mb-8">
        <div className="hospital-info">
          <h1 className="text-3xl font-bold text-[#0EAFBE] uppercase tracking-tight">{hospitalName}</h1>
          <p className="text-sm text-slate-600">Accra, Ghana · +233 302 123 456 · info@{hospitalName.toLowerCase().replace(/\s/g, '')}.gov.gh</p>
          <p className="text-xs text-slate-500 font-mono mt-1">Accredited by Ghana Health Service (GHS)</p>
        </div>
        <div className="text-right">
          <img src="/ghs-logo.png" alt="GHS" className="h-16 w-auto ml-auto opacity-80" />
        </div>
      </div>

      {/* Patient Identity Strip */}
      <div className="patient-strip bg-[#0EAFBE] text-white p-4 rounded-lg mb-8 flex justify-between">
        <div>
          <span className="text-xs uppercase opacity-80">Patient Name</span>
          <p className="text-lg font-bold">{patient.full_name}</p>
        </div>
        <div>
          <span className="text-xs uppercase opacity-80">Ghana Health ID</span>
          <p className="text-lg font-mono">{patient.ghana_health_id}</p>
        </div>
        <div>
          <span className="text-xs uppercase opacity-80">DOB / Gender</span>
          <p className="text-lg">{patient.date_of_birth} · {patient.gender}</p>
        </div>
        <div>
          <span className="text-xs uppercase opacity-80">Blood Group</span>
          <p className="text-lg font-bold">{patient.blood_group}</p>
        </div>
      </div>

      {/* Record Content */}
      <div className="record-section mb-10">
        <div className="section-title bg-slate-100 p-3 font-bold text-slate-800 border-l-4 border-[#0EAFBE] mb-6 uppercase text-sm tracking-widest">
          {record.record_type.replace(/_/g, ' ')} Details
        </div>
        
        <div className="space-y-4">
          <div className="flex border-b border-slate-100 py-3">
            <span className="w-1/3 font-semibold text-slate-600">Record ID</span>
            <span className="w-2/3 font-mono">{record.record_id}</span>
          </div>
          <div className="flex border-b border-slate-100 py-3">
            <span className="w-1/3 font-semibold text-slate-600">Date & Time</span>
            <span className="w-2/3">{new Date(record.created_at).toLocaleString()}</span>
          </div>
          <div className="flex border-b border-slate-100 py-3">
            <span className="w-1/3 font-semibold text-slate-600">Clinician</span>
            <span className="w-2/3 font-medium">{provider.full_name} ({provider.role})</span>
          </div>

          {/* Specific Record Type Data */}
          {record.record_type === 'diagnosis' && record.diagnosis && (
            <>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">ICD-10 Code</span>
                <span className="w-2/3 font-bold">{record.diagnosis.icd10_code}</span>
              </div>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">Description</span>
                <span className="w-2/3">{record.diagnosis.icd10_description}</span>
              </div>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">Clinical Notes</span>
                <span className="w-2/3 italic">{record.diagnosis.notes || "No notes provided."}</span>
              </div>
            </>
          )}

          {record.record_type === 'prescription' && record.prescription && (
            <>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">Medication</span>
                <span className="w-2/3 font-bold text-lg">{record.prescription.drug_name}</span>
              </div>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">Dosage & Freq</span>
                <span className="w-2/3">{record.prescription.dosage} · {record.prescription.frequency}</span>
              </div>
              <div className="flex border-b border-slate-100 py-3">
                <span className="w-1/3 font-semibold text-slate-600">Duration</span>
                <span className="w-2/3">{record.prescription.duration_days} days</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Verification / Sign-off */}
      <div className="mt-20 pt-10 border-t border-slate-200 grid grid-cols-2 gap-10">
        <div className="text-center">
          <div className="h-20 flex items-end justify-center mb-2">
            <img src="/signature-placeholder.png" alt="Signature" className="h-12 opacity-50" />
          </div>
          <div className="border-t border-slate-400 w-48 mx-auto pt-2">
            <p className="text-sm font-bold text-slate-800">{provider.full_name}</p>
            <p className="text-xs text-slate-500 uppercase">{provider.role}</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center">
          <div className="w-24 h-24 border-2 border-slate-200 rounded-lg flex items-center justify-center text-slate-200 text-xs text-center p-2 uppercase font-bold transform rotate-12">
            Hospital Official Stamp
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="print-footer fixed bottom-0 left-0 w-full text-center text-[8pt] text-slate-400 py-4 border-t border-slate-100">
        This is an official clinical document generated by MedSync EMR. Record Verification Hash: {record.record_id.slice(0, 8)}...
        <br />
        Generated on {new Date().toLocaleString()} by {provider.email}
      </div>
    </div>
  );
}
