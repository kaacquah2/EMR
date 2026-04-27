"use client";

import React, { useState, useRef } from "react";
import { useApi } from "@/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { AlertCircle, CheckCircle, Upload, Download, Loader2 } from "lucide-react";

interface BulkResult {
  order_id: string;
  result_value: string;
  reference_range: string;
  attachment_url?: string;
}

interface PreviewRow extends BulkResult {
  rowNum: number;
}

interface SubmissionDetail {
  order_id: string;
  status: "success" | "error";
  message: string;
}

interface SubmissionResult {
  submitted: number;
  failed: number;
  details: SubmissionDetail[];
}

export function LabBulkResultForm() {
  const api = useApi();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<BulkResult[]>([]);
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
        const requiredHeaders = ["order_id", "result_value", "reference_range"];
        const missingHeaders = requiredHeaders.filter((h) => !headers.includes(h));

        if (missingHeaders.length > 0) {
          setValidationErrors([
            `Missing required columns: ${missingHeaders.join(", ")}. Required: order_id, result_value, reference_range`,
          ]);
          return;
        }

        const errors: string[] = [];
        const data: BulkResult[] = [];

        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          const values = line.split(",").map((v) => v.trim());
          if (values.length < requiredHeaders.length) {
            errors.push(`Row ${i + 1}: Insufficient columns`);
            continue;
          }

          const row: BulkResult = {
            order_id: values[headers.indexOf("order_id")],
            result_value: values[headers.indexOf("result_value")],
            reference_range: values[headers.indexOf("reference_range")],
          };

          const attachmentIndex = headers.indexOf("attachment_url");
          if (attachmentIndex >= 0 && values[attachmentIndex]) {
            row.attachment_url = values[attachmentIndex];
          }

          // Validation
          if (!row.order_id) {
            errors.push(`Row ${i + 1}: order_id required`);
            continue;
          }
          if (!row.result_value) {
            errors.push(`Row ${i + 1}: result_value required`);
            continue;
          }
          if (!row.reference_range) {
            errors.push(`Row ${i + 1}: reference_range required`);
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
      "order_id,result_value,reference_range,attachment_url\n" +
      "550e8400-e29b-41d4-a716-446655440001,8.5,7.0-11.0,\n" +
      "550e8400-e29b-41d4-a716-446655440002,142,135-145,\n";

    const blob = new Blob([template], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "lab-bulk-submit-template.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const submitResults = async () => {
    if (csvData.length === 0) {
      setValidationErrors(["No data to submit"]);
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post<SubmissionResult>("/lab/results/bulk-submit", {
        results: csvData,
      });

      setSubmissionResult(response);
      setCsvData([]);
      setSelectedFile(null);
      setShowPreview(false);
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
              <p className="font-medium text-green-900">Submission successful</p>
              <p className="text-sm text-green-800 mt-1">
                {submissionResult.submitted} result(s) submitted, {submissionResult.failed} failed
              </p>
              {submissionResult.failed > 0 && (
                <div className="mt-3 bg-white rounded p-3 text-sm space-y-1 max-h-40 overflow-y-auto">
                  {submissionResult.details
                    .filter((d) => d.status === "error")
                    .map((d, idx) => (
                      <div key={idx} className="text-red-700">
                        <strong>{d.order_id}:</strong> {d.message}
                      </div>
                    ))}
                </div>
              )}
              <button
                type="button"
                onClick={resetForm}
                className="mt-3 px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
              >
                Submit another batch
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
              <h3 className="font-medium text-[#0F172A] mb-2">Upload CSV File</h3>
              <p className="text-sm text-[#64748B] mb-4">
                Required columns: <code className="bg-gray-100 px-1">order_id</code>,{" "}
                <code className="bg-gray-100 px-1">result_value</code>,{" "}
                <code className="bg-gray-100 px-1">reference_range</code>
              </p>

              <div className="border-2 border-dashed border-[#CBD5E1] rounded-lg p-8 text-center">
                <Upload className="h-8 w-8 text-[#64748B] mx-auto mb-2" />
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
                <p className="text-sm text-[#64748B] mt-2">or drag and drop</p>
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
                className="flex items-center gap-2 px-4 py-2 border border-[#CBD5E1] rounded hover:bg-[#F8FAFC] text-sm font-medium"
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
              <h3 className="font-medium text-[#0F172A]">Preview</h3>
              <p className="text-sm text-[#64748B]">Showing first 10 rows of {csvData.length} rows</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#CBD5E1]">
                    <th className="text-left py-2 px-2 font-medium">Row</th>
                    <th className="text-left py-2 px-2 font-medium">Order ID</th>
                    <th className="text-left py-2 px-2 font-medium">Result Value</th>
                    <th className="text-left py-2 px-2 font-medium">Reference Range</th>
                    <th className="text-left py-2 px-2 font-medium">Attachment</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row) => (
                    <tr key={row.rowNum} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                      <td className="py-2 px-2 text-[#64748B]">{row.rowNum}</td>
                      <td className="py-2 px-2 font-mono text-xs">{row.order_id.slice(0, 8)}...</td>
                      <td className="py-2 px-2">{row.result_value}</td>
                      <td className="py-2 px-2">{row.reference_range}</td>
                      <td className="py-2 px-2">
                        {row.attachment_url ? <Badge className="bg-blue-100 text-blue-700">PDF</Badge> : <span className="text-[#94A3B8]">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex gap-2 pt-4">
              <button
                type="button"
                onClick={submitResults}
                disabled={submitting}
                className="flex items-center gap-2 px-4 py-2 bg-[#0B8A96] text-white rounded hover:bg-[#097279] disabled:opacity-50 font-medium"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {submitting ? "Submitting..." : "Submit results"}
              </button>
              <button
                type="button"
                onClick={resetForm}
                disabled={submitting}
                className="px-4 py-2 border border-[#CBD5E1] rounded hover:bg-[#F8FAFC] disabled:opacity-50"
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
