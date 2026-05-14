"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLabResults } from "@/hooks/use-lab";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
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

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Lab Results Archive</h1>
        {results.length > 0 && (
          <button
            type="button"
            onClick={downloadResults}
            className="flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-700 rounded hover:bg-slate-50 dark:bg-slate-900 text-sm font-medium"
          >
            <Download className="h-4 w-4" />
            Download CSV
          </button>
        )}
      </div>

      {/* Filters */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-500 dark:text-slate-500" />
          <h3 className="font-medium text-slate-900 dark:text-slate-100">Filters</h3>
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
            <label className="text-sm font-medium text-slate-900 dark:text-slate-100">Status</label>
            <div className="flex flex-wrap gap-2">
              {["resulted", "verified", "pending"].map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => toggleStatusFilter(status)}
                  className={`px-2 py-1 rounded text-sm font-medium transition ${
                    statusFilter.includes(status)
                      ? "bg-[#0B8A96] text-white"
                      : "bg-slate-100 dark:bg-slate-900 text-slate-900 dark:text-slate-100 hover:bg-slate-200 dark:bg-slate-800"
                  }`}
                >
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Date From */}
          <div className="space-y-2">
            <label htmlFor="date-from" className="text-sm font-medium text-slate-900 dark:text-slate-100">
              From
            </label>
            <input
              id="date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full px-3 py-1 border border-slate-300 dark:border-slate-700 rounded text-sm"
            />
          </div>

          {/* Date To */}
          <div className="space-y-2">
            <label htmlFor="date-to" className="text-sm font-medium text-slate-900 dark:text-slate-100">
              To
            </label>
            <input
              id="date-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full px-3 py-1 border border-slate-300 dark:border-slate-700 rounded text-sm"
            />
          </div>
        </div>
      </Card>

      {/* Results */}
      <Card className="p-6">
        {loading ? (
          <p className="text-slate-500 dark:text-slate-500">Loading...</p>
        ) : results.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-500">No results found.</p>
        ) : (
          <div className="space-y-4">
            {/* Results Table */}
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>GHA ID</TableHead>
                    <TableHead>Test</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Lab Tech</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <p className="font-medium text-slate-900 dark:text-white">{r.patient_name}</p>
                      </TableCell>
                      <TableCell className="text-slate-500 dark:text-slate-400">{r.gha_id}</TableCell>
                      <TableCell className="text-slate-900 dark:text-white">{r.test_name}</TableCell>
                      <TableCell className="font-medium">{r.result_value}</TableCell>
                      <TableCell className="text-slate-500 dark:text-slate-400">{r.reference_range}</TableCell>
                      <TableCell>
                        <Badge className={statusBadgeClass(r.status)}>
                          {r.status.charAt(0).toUpperCase() + r.status.slice(1)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-slate-500 dark:text-slate-400">{r.lab_tech_name}</TableCell>
                      <TableCell className="text-slate-500 dark:text-slate-400">{r.created_at?.split("T")[0]}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
              <Pagination
                total={total}
                limit={limit}
                offset={offset}
                onOffsetChange={setOffset}
              />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
