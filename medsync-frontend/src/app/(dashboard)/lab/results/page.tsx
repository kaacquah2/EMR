"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLabResults } from "@/hooks/use-lab";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Download, Filter, X } from "lucide-react";

export default function LabResultsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const canAccess = user?.role === "lab_technician";

  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  const filters = useMemo(
    () => ({
      status: statusFilter,
      date_from: dateFrom,
      date_to: dateTo,
    }),
    [statusFilter, dateFrom, dateTo]
  );

  const { results, total, loading, limit, offset, setOffset } = useLabResults(filters);

  const statusBadgeClass = (status: string) => {
    switch (status) {
      case "resulted":
        return "bg-blue-100 text-blue-700";
      case "verified":
        return "bg-green-100 text-green-700";
      case "pending":
        return "bg-yellow-100 text-yellow-700";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  const toggleStatusFilter = (status: string) => {
    setStatusFilter((prev) => (prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]));
  };

  const clearFilters = () => {
    setStatusFilter([]);
    setDateFrom("");
    setDateTo("");
  };

  const downloadResults = () => {
    if (results.length === 0) {
      alert("No results to download");
      return;
    }

    const csv = [
      ["Patient Name", "GHA ID", "Test Name", "Result Value", "Reference Range", "Status", "Lab Tech", "Created At"],
      ...results.map((r) => [r.patient_name, r.gha_id, r.test_name, r.result_value, r.reference_range, r.status, r.lab_tech_name, r.created_at?.split("T")[0]]),
    ]
      .map((row) => row.map((cell) => `"${cell}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lab-results-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">Lab Results Archive</h1>
        {results.length > 0 && (
          <button
            type="button"
            onClick={downloadResults}
            className="flex items-center gap-2 px-4 py-2 border border-[#CBD5E1] rounded hover:bg-[#F8FAFC] text-sm font-medium"
          >
            <Download className="h-4 w-4" />
            Download CSV
          </button>
        )}
      </div>

      {/* Filters */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-[#64748B]" />
          <h3 className="font-medium text-[#0F172A]">Filters</h3>
          {(statusFilter.length > 0 || dateFrom || dateTo) && (
            <button
              type="button"
              onClick={clearFilters}
              className="ml-auto text-sm text-red-600 hover:text-red-700 flex items-center gap-1"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          {/* Status Filter */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-[#0F172A]">Status</label>
            <div className="flex flex-wrap gap-2">
              {["resulted", "verified", "pending"].map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => toggleStatusFilter(status)}
                  className={`px-2 py-1 rounded text-sm font-medium transition ${
                    statusFilter.includes(status)
                      ? "bg-[#0B8A96] text-white"
                      : "bg-[#F1F5F9] text-[#0F172A] hover:bg-[#E2E8F0]"
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Date From */}
          <div className="space-y-2">
            <label htmlFor="date-from" className="text-sm font-medium text-[#0F172A]">
              From
            </label>
            <input
              id="date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full px-3 py-1 border border-[#CBD5E1] rounded text-sm"
            />
          </div>

          {/* Date To */}
          <div className="space-y-2">
            <label htmlFor="date-to" className="text-sm font-medium text-[#0F172A]">
              To
            </label>
            <input
              id="date-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full px-3 py-1 border border-[#CBD5E1] rounded text-sm"
            />
          </div>
        </div>
      </Card>

      {/* Results */}
      <Card className="p-6">
        {loading ? (
          <p className="text-[#64748B]">Loading...</p>
        ) : results.length === 0 ? (
          <p className="text-[#64748B]">No results found.</p>
        ) : (
          <div className="space-y-4">
            {/* Results Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#CBD5E1]">
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Patient</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">GHA ID</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Test</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Result</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Reference</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Status</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Lab Tech</th>
                    <th className="text-left py-3 px-2 font-medium text-[#0F172A]">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.id} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                      <td className="py-3 px-2">
                        <p className="font-medium text-[#0F172A]">{r.patient_name}</p>
                      </td>
                      <td className="py-3 px-2 text-[#64748B]">{r.gha_id}</td>
                      <td className="py-3 px-2 text-[#0F172A]">{r.test_name}</td>
                      <td className="py-3 px-2 font-medium">{r.result_value}</td>
                      <td className="py-3 px-2 text-[#64748B]">{r.reference_range}</td>
                      <td className="py-3 px-2">
                        <Badge className={statusBadgeClass(r.status)}>
                          {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                        </Badge>
                      </td>
                      <td className="py-3 px-2 text-[#64748B]">{r.lab_tech_name}</td>
                      <td className="py-3 px-2 text-[#64748B]">{r.created_at?.split("T")[0]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between pt-4 border-t border-[#CBD5E1]">
              <p className="text-sm text-[#64748B]">
                Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} results
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="px-3 py-1 border border-[#CBD5E1] rounded hover:bg-[#F8FAFC] disabled:opacity-50 text-sm"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total}
                  className="px-3 py-1 border border-[#CBD5E1] rounded hover:bg-[#F8FAFC] disabled:opacity-50 text-sm"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
