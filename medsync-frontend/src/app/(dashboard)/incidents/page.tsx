"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { AlertCircle, Plus, Loader2, RefreshCw, ShieldAlert } from "lucide-react";

const CATEGORIES = [
  "medication",
  "fall",
  "procedure",
  "equipment",
  "documentation",
  "infection_control",
  "communication",
  "other",
];

const SEVERITIES = [
  { value: "near_miss", label: "Near Miss" },
  { value: "minor", label: "Minor" },
  { value: "moderate", label: "Moderate" },
  { value: "serious", label: "Serious" },
  { value: "critical", label: "Critical" },
];

interface Incident {
  id: string;
  category: string;
  severity: string;
  status: string;
  incident_datetime: string;
  ward: string | null;
  patient_id: string | null;
  reported_by: string;
  description: string;
  created_at: string;
}

const severityVariant: Record<string, "default" | "active" | "pending" | "success"> = {
  near_miss: "default",
  minor: "default",
  moderate: "pending",
  serious: "active",
  critical: "active",
};

function ReportIncidentModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const api = useApi();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    category: "medication",
    severity: "minor",
    incident_datetime: new Date().toISOString().slice(0, 16),
    description: "",
    location: "",
    immediate_actions: "",
    is_anonymous: false,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.description.trim()) {
      toast.error("Description is required");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/incidents", {
        ...form,
        incident_datetime: new Date(form.incident_datetime).toISOString(),
      });
      toast.success("Incident reported successfully");
      onSuccess();
    } catch {
      toast.error("Failed to submit incident report");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-xl p-6 shadow-2xl border border-slate-200 dark:border-slate-800 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center gap-2 mb-4">
          <ShieldAlert className="h-5 w-5 text-rose-500" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Report Clinical Incident</h3>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Category <span className="text-rose-500">*</span>
              </label>
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                required
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Severity <span className="text-rose-500">*</span>
              </label>
              <select
                value={form.severity}
                onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
                className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100"
                required
              >
                {SEVERITIES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Date & Time of Incident <span className="text-rose-500">*</span>
            </label>
            <Input
              type="datetime-local"
              value={form.incident_datetime}
              onChange={(e) => setForm((f) => ({ ...f, incident_datetime: e.target.value }))}
              required
              className="bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Describe what happened, who was involved, and the sequence of events..."
              rows={4}
              required
              className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 resize-y focus:outline-none focus:ring-2 focus:ring-[#6366F1]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Location
            </label>
            <Input
              type="text"
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="Ward, room, corridor, etc."
              className="bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Immediate Actions Taken
            </label>
            <textarea
              value={form.immediate_actions}
              onChange={(e) => setForm((f) => ({ ...f, immediate_actions: e.target.value }))}
              placeholder="What was done immediately after the incident?"
              rows={2}
              className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 resize-y focus:outline-none focus:ring-2 focus:ring-[#6366F1]"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="anonymous"
              checked={form.is_anonymous}
              onChange={(e) => setForm((f) => ({ ...f, is_anonymous: e.target.checked }))}
              className="h-4 w-4 rounded border-slate-300 text-[#6366F1]"
            />
            <label htmlFor="anonymous" className="text-sm text-slate-600 dark:text-slate-400">
              Submit anonymously (your name will not be attached to the report)
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              className="bg-rose-600 hover:bg-rose-700 text-white"
              disabled={submitting}
            >
              {submitting ? (
                <><Loader2 className="h-3 w-3 animate-spin mr-1" /> Submitting...</>
              ) : (
                "Submit Report"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function IncidentsPage() {
  const { user } = useAuth();
  const api = useApi();
  const toast = useToast();

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const isAdmin = user?.role === "hospital_admin" || user?.role === "super_admin";
  const canReport = ["nurse", "doctor", "lab_technician", "hospital_admin", "super_admin"].includes(
    user?.role ?? ""
  );

  const fetchIncidents = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (severityFilter) params.set("severity", severityFilter);
      if (categoryFilter) params.set("category", categoryFilter);
      const res = await api.get<{ incidents: Incident[]; total: number }>(
        `/incidents/list?${params.toString()}`
      );
      setIncidents(res.incidents ?? []);
    } catch {
      toast.error("Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [api, isAdmin, severityFilter, categoryFilter, toast]);

  useEffect(() => {
    void fetchIncidents();
  }, [fetchIncidents]);

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Incidents" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Clinical Incident Reporting
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {isAdmin
              ? "Review and manage reported clinical incidents across the facility."
              : "Report a clinical incident for review by hospital administration."}
          </p>
        </div>
        {canReport && (
          <Button
            onClick={() => setShowReportModal(true)}
            className="bg-rose-600 hover:bg-rose-700 text-white flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" />
            Report Incident
          </Button>
        )}
      </div>

      {/* Admin: Incident List */}
      {isAdmin && (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800">
            <CardTitle>Incident Log</CardTitle>
            <div className="flex flex-wrap gap-2">
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100"
              >
                <option value="">All severities</option>
                {SEVERITIES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100"
              >
                <option value="">All categories</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </option>
                ))}
              </select>
              <Button variant="secondary" size="sm" onClick={() => void fetchIncidents()} disabled={loading}>
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex justify-center items-center py-12 text-slate-500">
                <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading incidents...
              </div>
            ) : incidents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2">
                <AlertCircle className="h-8 w-8" />
                <p className="text-sm">No incidents reported matching these filters.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50/50 dark:bg-slate-800/10 text-slate-500 font-semibold border-b border-slate-100 dark:border-slate-800 uppercase tracking-wider text-xs">
                      <th className="px-4 py-3 text-left">Date/Time</th>
                      <th className="px-4 py-3 text-left">Category</th>
                      <th className="px-4 py-3 text-left">Severity</th>
                      <th className="px-4 py-3 text-left">Ward</th>
                      <th className="px-4 py-3 text-left">Reported By</th>
                      <th className="px-4 py-3 text-left">Description</th>
                      <th className="px-4 py-3 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {incidents.map((inc) => (
                      <tr key={inc.id} className="hover:bg-slate-50/30 dark:hover:bg-slate-900/30">
                        <td className="px-4 py-3 whitespace-nowrap text-slate-500 text-xs">
                          {new Date(inc.incident_datetime).toLocaleString("en-GB", {
                            day: "numeric", month: "short", year: "numeric",
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </td>
                        <td className="px-4 py-3 capitalize text-slate-700 dark:text-slate-300">
                          {inc.category.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={severityVariant[inc.severity] ?? "default"}>
                            {inc.severity.replace(/_/g, " ")}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-500 text-xs">{inc.ward ?? "—"}</td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">
                          {inc.reported_by}
                        </td>
                        <td className="px-4 py-3 text-slate-700 dark:text-slate-300 max-w-[260px]">
                          <span title={inc.description}>
                            {inc.description.slice(0, 100)}{inc.description.length > 100 ? "…" : ""}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={inc.status === "open" ? "active" : "success"}>
                            {inc.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Non-admin: informational message */}
      {!isAdmin && canReport && (
        <Card>
          <CardContent className="pt-6 text-center space-y-3">
            <ShieldAlert className="h-10 w-10 text-rose-400 mx-auto" />
            <p className="text-slate-600 dark:text-slate-400 text-sm">
              Use the <strong>Report Incident</strong> button above to submit a clinical incident report.
              Your report will be reviewed by hospital administration.
            </p>
            <p className="text-xs text-slate-400">
              Reports can be submitted anonymously. Serious and critical incidents notify hospital administration immediately.
            </p>
          </CardContent>
        </Card>
      )}

      {showReportModal && (
        <ReportIncidentModal
          onClose={() => setShowReportModal(false)}
          onSuccess={() => {
            setShowReportModal(false);
            void fetchIncidents();
          }}
        />
      )}
    </div>
  );
}
