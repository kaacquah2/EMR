"use client";
import React, { useCallback, useEffect, useState, useMemo } from "react";
import {
  FileText,
  Activity,
  Image as ImageIcon,
  Search,
  RefreshCw,
  Play,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Loader2
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";

interface RadiologyOrder {
  order_id: string;
  patient_id: string;
  patient_name: string;
  study_type: string;
  status: "ordered" | "in_progress" | "completed";
  attachment_url: string | null;
  created_at: string | null;
}

export function RadiologyDashboard() {
  const api = useApi();
  const toast = useToast();

  const [orders, setOrders] = useState<RadiologyOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Search & Filtering State
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "ordered" | "in_progress" | "completed">("all");

  // Modal/Action State
  const [selectedOrder, setSelectedOrder] = useState<RadiologyOrder | null>(null);
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [submittingAction, setSubmittingAction] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Load orders
  const fetchOrders = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const response = await api.get<{ data: RadiologyOrder[] }>("/records/radiology-order");
      setOrders(response.data || []);
    } catch (err) {
      if (!isBenignApiNetworkFailure(err)) {
        console.error("Error fetching radiology orders:", err);
      }
      setError("Failed to fetch radiology orders. Please check your connection.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);
  usePollWhenVisible(() => fetchOrders(true), 30_000, true);

  // Stats calculation
  const stats = useMemo(() => {
    const total = orders.length;
    const ordered = orders.filter((o) => o.status === "ordered").length;
    const inProgress = orders.filter((o) => o.status === "in_progress").length;
    const completed = orders.filter((o) => o.status === "completed").length;
    return { total, ordered, inProgress, completed };
  }, [orders]);

  // Filter and search logic
  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      const matchTab = activeTab === "all" || o.status === activeTab;
      const matchSearch =
        !searchQuery.trim() ||
        o.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        o.study_type.toLowerCase().includes(searchQuery.toLowerCase());
      return matchTab && matchSearch;
    });
  }, [orders, activeTab, searchQuery]);

  // Start study action
  const handleStartStudy = async (orderId: string, patientName: string) => {
    try {
      setSubmittingAction(true);
      await api.post(`/records/radiology-order/${orderId}/attachment`, {
        status: "in_progress"
      });
      toast.success(`Started scan/study for ${patientName}`);
      void fetchOrders(true);
    } catch (err) {
      console.error("Failed to start study:", err);
      toast.error("Failed to start study. Please try again.");
    } finally {
      setSubmittingAction(false);
    }
  };

  // Complete study submit
  const handleCompleteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder) return;
    if (!attachmentUrl.trim()) {
      toast.error("PACS Scan/Attachment URL is required.");
      return;
    }

    try {
      setSubmittingAction(true);
      await api.post(`/records/radiology-order/${selectedOrder.order_id}/attachment`, {
        status: "completed",
        attachment_url: attachmentUrl.trim()
      });
      toast.success(`Completed study and uploaded scan for ${selectedOrder.patient_name}`);
      setIsModalOpen(false);
      setSelectedOrder(null);
      setAttachmentUrl("");
      void fetchOrders(true);
    } catch (err) {
      console.error("Failed to complete study:", err);
      toast.error("Failed to save study results.");
    } finally {
      setSubmittingAction(false);
    }
  };

  // Open modal
  const openCompleteModal = (order: RadiologyOrder) => {
    setSelectedOrder(order);
    setAttachmentUrl(order.attachment_url || "");
    setIsModalOpen(true);
  };

  // Status badges mapping
  const getStatusBadge = (status: RadiologyOrder["status"]) => {
    switch (status) {
      case "ordered":
        return <Badge variant="pending">Awaiting Scan</Badge>;
      case "in_progress":
        return <Badge variant="default" className="bg-indigo-100 text-indigo-800 border-indigo-200">Scanning</Badge>;
      case "completed":
        return <Badge variant="success">Completed</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Title block */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold font-sora text-slate-900 dark:text-slate-100">
            Radiology & Imaging Console
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Manage diagnostic radiology orders, PACS image linking, and study completion.
          </p>
        </div>
        <Button
          onClick={() => void fetchOrders(true)}
          variant="secondary"
          size="sm"
          className="flex items-center gap-1.5"
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm border-l-4 border-l-[#6366F1]">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Total Studies</p>
                <p className="text-2xl font-black mt-1 text-slate-850 dark:text-slate-100">{stats.total}</p>
              </div>
              <div className="p-2 bg-[#6366F1]/10 rounded-lg">
                <FileText className="h-5 w-5 text-[#6366F1]" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm border-l-4 border-l-[#EF9F27]">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Awaiting Scan</p>
                <p className="text-2xl font-black mt-1 text-[#EF9F27]">{stats.ordered}</p>
              </div>
              <div className="p-2 bg-[#EF9F27]/10 rounded-lg">
                <Activity className="h-5 w-5 text-[#EF9F27]" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm border-l-4 border-l-indigo-500">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">In Progress</p>
                <p className="text-2xl font-black mt-1 text-indigo-600 dark:text-indigo-400">{stats.inProgress}</p>
              </div>
              <div className="p-2 bg-indigo-500/10 rounded-lg">
                <ImageIcon className="h-5 w-5 text-indigo-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm border-l-4 border-l-[#10B981]">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Completed Today</p>
                <p className="text-2xl font-black mt-1 text-[#10B981]">{stats.completed}</p>
              </div>
              <div className="p-2 bg-[#10B981]/10 rounded-lg">
                <CheckCircle2 className="h-5 w-5 text-[#10B981]" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Order Registry */}
      <Card className="shadow-sm border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <CardHeader className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-slate-100 dark:border-slate-800 gap-4">
          <div>
            <CardTitle className="text-lg">Imaging Studies Worklist</CardTitle>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search patient/study..."
                className="pl-9 w-[240px] bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="flex gap-2 border-b border-slate-100 dark:border-slate-800 px-6 py-2 bg-slate-50/50 dark:bg-slate-950/20">
            {[
              ["all", "All Cases"],
              ["ordered", "Awaiting Scan"],
              ["in_progress", "In Progress"],
              ["completed", "Completed"]
            ].map(([val, label]) => (
              <button
                key={val}
                onClick={() => setActiveTab(val as typeof activeTab)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  activeTab === val
                    ? "bg-[#6366F1] text-white"
                    : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {loading && orders.length === 0 ? (
            <div className="flex justify-center items-center py-12 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading imaging orders...
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-rose-500 gap-2">
              <AlertCircle className="h-8 w-8" />
              <span>{error}</span>
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No radiology orders found matching this criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50/50 dark:bg-slate-800/10 text-slate-500 font-semibold border-b border-slate-100 dark:border-slate-800 uppercase tracking-wider text-xs">
                    <th className="px-6 py-4 text-left">Patient</th>
                    <th className="px-6 py-4 text-left">Study Type</th>
                    <th className="px-6 py-4 text-left">Ordered Date</th>
                    <th className="px-6 py-4 text-left">Status</th>
                    <th className="px-6 py-4 text-left">Result Link</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-150 dark:divide-slate-850">
                  {filteredOrders.map((o) => (
                    <tr key={o.order_id} className="hover:bg-slate-50/30 dark:hover:bg-slate-900/30 transition-colors">
                      <td className="px-6 py-4">
                        <span className="font-bold text-slate-900 dark:text-slate-100">{o.patient_name}</span>
                      </td>
                      <td className="px-6 py-4 text-slate-700 dark:text-slate-300 font-medium">
                        {o.study_type}
                      </td>
                      <td className="px-6 py-4 text-slate-500 whitespace-nowrap">
                        {o.created_at ? new Date(o.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(o.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {o.attachment_url ? (
                          <a
                            href={o.attachment_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[#6366F1] font-semibold hover:underline"
                          >
                            View PACS Scan <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-slate-400 text-xs italic">No scan linked</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right whitespace-nowrap space-x-1">
                        {o.status === "ordered" && (
                          <Button
                            size="sm"
                            className="bg-[#6366F1] hover:bg-[#4F46E5] text-white flex inline-flex items-center gap-1"
                            onClick={() => void handleStartStudy(o.order_id, o.patient_name)}
                            disabled={submittingAction}
                          >
                            <Play className="h-3 w-3" /> Start Scan
                          </Button>
                        )}
                        {o.status === "in_progress" && (
                          <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                            onClick={() => openCompleteModal(o)}
                            disabled={submittingAction}
                          >
                            Link PACS Scan
                          </Button>
                        )}
                        {o.status === "completed" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-slate-300 text-slate-600 hover:bg-slate-50"
                            onClick={() => openCompleteModal(o)}
                            disabled={submittingAction}
                          >
                            Update URL
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Attach Scan / Complete Study Modal */}
      {isModalOpen && selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl p-6 shadow-2xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">
              Attach PACS Scan & Complete Study
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Enter the secure viewer or cloud PACS URL containing the imaging study result files for <strong>{selectedOrder.patient_name}</strong>.
            </p>

            <form onSubmit={handleCompleteSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
                  PACS/Attachment URL
                </label>
                <Input
                  type="url"
                  placeholder="https://pacs.hospital.gov.gh/viewer/..."
                  value={attachmentUrl}
                  onChange={(e) => setAttachmentUrl(e.target.value)}
                  className="w-full bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-mono text-xs"
                  required
                  autoFocus
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setIsModalOpen(false);
                    setSelectedOrder(null);
                  }}
                  disabled={submittingAction}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  disabled={submittingAction}
                >
                  {submittingAction ? "Saving..." : "Save scan & complete"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
