"use client";

import React, { useState, useRef } from "react";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { AlertCircle, CheckCircle, Upload, Download, Loader2 } from "lucide-react";

interface BulkAppointmentRow {
  patient_id: string;
  scheduled_at: string;
  department_id?: string;
  doctor_id?: string;
  appointment_type?: string;
  notes?: string;
}

interface PreviewRow extends BulkAppointmentRow {
  rowNum: number;
}

interface SubmissionDetail {
  row_num?: number;
  patient_id?: string;
  status: "success" | "error";
  message: string;
  appointment_id?: string;
}

interface SubmissionResult {
  created: number;
  failed: number;
  details: SubmissionDetail[];
}

export interface AppointmentBulkImportFormProps {
  onSuccess?: () => void;
}

export default function AppointmentBulkImportForm({ onSuccess }: AppointmentBulkImportFormProps) {
  const api = useApi();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<BulkAppointmentRow[]>([]);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const parseCSV = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        const lines = text.split("\n");
        if (lines.length < 2) {
          setValidationErrors(["CSV must contain header and at least one data row"]);
          return;
        }

        const headers = lines[0].split(",").map((h) => h.trim().toLowerCase());
        const requiredHeaders = ["patient_id", "scheduled_at"];
        const missingHeaders = requiredHeaders.filter((h) => !headers.includes(h));

        if (missingHeaders.length > 0) {
          setValidationErrors([
            `Missing required columns: ${missingHeaders.join(", ")}. Required: patient_id, scheduled_at`,
          ]);
          return;
        }

        const errors: string[] = [];
        const data: BulkAppointmentRow[] = [];

        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          const values = line.split(",").map((v) => v.trim());
          if (values.length < requiredHeaders.length) {
            errors.push(`Row ${i + 1}: Insufficient columns`);
            continue;
          }

          const row: BulkAppointmentRow = {
            patient_id: values[headers.indexOf("patient_id")],
            scheduled_at: values[headers.indexOf("scheduled_at")],
          };

          // Optional fields
          const deptIndex = headers.indexOf("department_id");
          if (deptIndex >= 0 && values[deptIndex]) {
            row.department_id = values[deptIndex];
          }

          const doctorIndex = headers.indexOf("doctor_id");
          if (doctorIndex >= 0 && values[doctorIndex]) {
            row.doctor_id = values[doctorIndex];
          }

          const typeIndex = headers.indexOf("appointment_type");
          if (typeIndex >= 0 && values[typeIndex]) {
            row.appointment_type = values[typeIndex];
          }

          const notesIndex = headers.indexOf("notes");
          if (notesIndex >= 0 && values[notesIndex]) {
            row.notes = values[notesIndex];
          }

          // Validation
          if (!row.patient_id) {
            errors.push(`Row ${i + 1}: patient_id required`);
            continue;
          }
          if (!row.scheduled_at) {
            errors.push(`Row ${i + 1}: scheduled_at required (format: YYYY-MM-DD HH:MM)`);
            continue;
          }

          // Validate datetime format
          if (!row.scheduled_at.match(/^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}$/)) {
            errors.push(`Row ${i + 1}: Invalid datetime format (use YYYY-MM-DD HH:MM)`);
            continue;
          }

          data.push(row);
        }

        if (errors.length > 0) {
          setValidationErrors(errors);
        } else {
          setValidationErrors([]);
        }

        setCsvData(data);
        setPreviewRows(data.slice(0, 10).map((r, idx) => ({ ...r, rowNum: idx + 1 })));
        setShowPreview(true);
        setSelectedFile(file);
      } catch (err) {
        setValidationErrors([`Failed to parse CSV: ${err instanceof Error ? err.message : "Unknown error"}`]);
      }
    };

    reader.readAsText(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith(".csv")) {
        setValidationErrors(["Please select a CSV file"]);
        return;
      }
      parseCSV(file);
    }
  };

  const downloadTemplate = () => {
    const template =
      "patient_id,scheduled_at,department_id,doctor_id,appointment_type,notes\n" +
      "550e8400-e29b-41d4-a716-446655440001,2026-04-15 09:00,,550e8400-e29b-41d4-a716-446655440099,General,Follow-up\n" +
      "550e8400-e29b-41d4-a716-446655440002,2026-04-15 10:30,,550e8400-e29b-41d4-a716-446655440099,Consultation,New patient\n";

    const blob = new Blob([template], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "appointment-bulk-import-template.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const submitAppointments = async () => {
    if (csvData.length === 0) {
      setValidationErrors(["No data to submit"]);
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post<SubmissionResult>("/appointments/bulk-import", {
        appointments: csvData,
      });

      setSubmissionResult(response);
      setCsvData([]);
      setSelectedFile(null);
      setShowPreview(false);
      
      if (onSuccess) {
        // Call onSuccess after a short delay to show the success message
        setTimeout(onSuccess, 1500);
      }
    } catch (err) {
      setValidationErrors([
        `Submission failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      ]);
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setCsvData([]);
    setSelectedFile(null);
    setShowPreview(false);
    setValidationErrors([]);
    setSubmissionResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      {/* Success Result */}
      {submissionResult && (
        <Card className="border-green-200 bg-green-50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-green-900">Import successful</p>
              <p className="text-sm text-green-800 mt-1">
                {submissionResult.created} appointment(s) created, {submissionResult.failed} failed
              </p>
              {submissionResult.failed > 0 && (
                <div className="mt-3 bg-white rounded p-3 text-sm space-y-1 max-h-40 overflow-y-auto">
                  {submissionResult.details
                    .filter((d) => d.status === "error")
                    .map((d, idx) => (
                      <div key={idx} className="text-red-700">
                        <strong>Row {d.row_num}:</strong> {d.message}
                      </div>
                    ))}
                </div>
              )}
              <button
                type="button"
                onClick={resetForm}
                className="mt-3 px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
              >
                Import another batch
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <Card className="border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-red-900">Validation errors</p>
              <ul className="text-sm text-red-800 mt-2 space-y-1 list-disc list-inside max-h-40 overflow-y-auto">
                {validationErrors.map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      )}

      {/* Upload Section */}
      {!showPreview && !submissionResult && (
        <Card className="p-6">
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-slate-900 dark:text-slate-100 mb-2">Upload Appointment CSV</h3>
              <p className="text-sm text-slate-500 dark:text-slate-500 mb-4">
                Required columns: <code className="bg-gray-100 px-1">patient_id</code>,{" "}
                <code className="bg-gray-100 px-1">scheduled_at</code> (YYYY-MM-DD HH:MM)
              </p>

              <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-8 text-center">
                <Upload className="h-8 w-8 text-slate-500 dark:text-slate-500 mx-auto mb-2" />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-[#0B8A96] hover:text-[#097279] font-medium underline"
                >
                  Click to upload
                </button>
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-2">or drag and drop</p>
                {selectedFile && (
                  <p className="text-sm text-green-600 mt-2">
                    ✓ {selectedFile.name} ({selectedFile.size} bytes)
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={downloadTemplate}
                className="flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-700 rounded hover:bg-slate-50 dark:bg-slate-900 text-sm font-medium"
              >
                <Download className="h-4 w-4" />
                Download template
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Preview Section */}
      {showPreview && !submissionResult && (
        <Card className="p-6">
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-slate-900 dark:text-slate-100">Preview</h3>
              <p className="text-sm text-slate-500 dark:text-slate-500">Showing first 10 rows of {csvData.length} rows</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-300 dark:border-slate-700">
                    <th className="text-left py-2 px-2 font-medium">Row</th>
                    <th className="text-left py-2 px-2 font-medium">Patient ID</th>
                    <th className="text-left py-2 px-2 font-medium">Scheduled At</th>
                    <th className="text-left py-2 px-2 font-medium">Department</th>
                    <th className="text-left py-2 px-2 font-medium">Doctor</th>
                    <th className="text-left py-2 px-2 font-medium">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row) => (
                    <tr key={row.rowNum} className="border-b border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900">
                      <td className="py-2 px-2 text-slate-500 dark:text-slate-500">{row.rowNum}</td>
                      <td className="py-2 px-2 font-mono text-xs">{row.patient_id.slice(0, 8)}...</td>
                      <td className="py-2 px-2">{row.scheduled_at}</td>
                      <td className="py-2 px-2 text-slate-500 dark:text-slate-500">{row.department_id ? row.department_id.slice(0, 8) : "—"}</td>
                      <td className="py-2 px-2 text-slate-500 dark:text-slate-500">{row.doctor_id ? row.doctor_id.slice(0, 8) : "—"}</td>
                      <td className="py-2 px-2">{row.appointment_type || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex gap-2 pt-4">
              <button
                type="button"
                onClick={submitAppointments}
                disabled={submitting}
                className="flex items-center gap-2 px-4 py-2 bg-[#0B8A96] text-white rounded hover:bg-[#097279] disabled:opacity-50 font-medium"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {submitting ? "Creating..." : "Create appointments"}
              </button>
              <button
                type="button"
                onClick={resetForm}
                disabled={submitting}
                className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded hover:bg-slate-50 dark:bg-slate-900 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
