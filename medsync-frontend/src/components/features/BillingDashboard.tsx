"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { 
  ClipboardCheck, 
  AlertCircle, 
  Clock, 
  TrendingUp,
  FileSearch,
  Filter,
  Download,
  CheckCircle2,
  XCircle,
  Plus,
  Search,
  DollarSign,
  FileText,
  CreditCard,
  Layers,
  ChevronRight,
  Loader2,
  Check
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { 
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
  DialogPortal,
  DialogOverlay
} from "@/components/ui/dialog";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  BarChart,
  Bar,
  Cell
} from "recharts";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";

// Invoice interface
interface InvoiceItem {
  description: string;
  quantity: number;
  unit_price: number; // in cents
  service_type: string;
}

interface Invoice {
  id: string;
  patient_id: string;
  patient_name: string;
  amount_cents: number;
  currency: string;
  status: "draft" | "issued" | "paid" | "partial" | "cancelled" | "pending" | "partially_paid";
  notes?: string | null;
  created_at: string;
  paid_at?: string | null;
  payment_method: "cash" | "card" | "nhis" | "insurance";
  paid_amount: number; // GHS
  nhis_claim_status?: string | null;
  nhis_claim_reference?: string | null;
}

interface DashboardMetrics {
  today: {
    revenue: number;
    invoices_created: number;
  };
  outstanding: {
    count: number;
    amount: number;
  };
  nhis: {
    pending: number;
    approved_this_month: number;
    rejected_this_month: number;
  };
  weekly_trend: Array<{
    date: string;
    revenue: number;
  }>;
}

interface PatientSearchRow {
  patient_id: string;
  full_name: string;
  ghana_health_id: string;
  nhis_number?: string | null;
  phone?: string | null;
}

export function BillingDashboard() {
  const api = useApi();
  const toast = useToast();

  // Dashboard state
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [loadingInvoices, setLoadingInvoices] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [invoicesError, setInvoicesError] = useState<string | null>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState("overview");

  // Modals state
  const [isCreateInvoiceOpen, setIsCreateInvoiceOpen] = useState(false);
  const [isRecordPaymentOpen, setIsRecordPaymentOpen] = useState(false);
  const [isSubmitNhisOpen, setIsSubmitNhisOpen] = useState(false);

  // Active invoice context for actions
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  // Create Invoice Form State
  const [patientSearchQuery, setPatientSearchQuery] = useState("");
  const [patientSearchResults, setPatientSearchResults] = useState<PatientSearchRow[]>([]);
  const [searchingPatients, setSearchingPatients] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<PatientSearchRow | null>(null);
  
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "card" | "nhis" | "insurance">("cash");
  const [invoiceNotes, setInvoiceNotes] = useState("");
  const [invoiceItems, setInvoiceItems] = useState<Array<{ description: string; quantity: number; priceGhs: string; serviceType: string }>>([
    { description: "General Consultation", quantity: 1, priceGhs: "50.00", serviceType: "CONSULTATION" }
  ]);
  const [submittingInvoice, setSubmittingInvoice] = useState(false);

  // Record Payment Form State
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [paymentNotes, setPaymentNotes] = useState("");
  const [submittingPayment, setSubmittingPayment] = useState(false);

  // Submit NHIS Claim Form State
  const [nhisMemberId, setNhisMemberId] = useState("");
  const [diagnosisCodes, setDiagnosisCodes] = useState("A09, B54"); // Malaria, gastroenteritis defaults
  const [checkEligibility, setCheckEligibility] = useState(true);
  const [submittingNhis, setSubmittingNhis] = useState(false);

  // Invoice Filter State
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchFilter, setSearchFilter] = useState("");

  // Fetch Dashboard Metrics
  const fetchMetrics = useCallback(async () => {
    try {
      setLoadingMetrics(true);
      const res = await api.get<DashboardMetrics>("/billing/dashboard");
      setMetrics(res);
      setMetricsError(null);
    } catch (err) {
      if (!isBenignApiNetworkFailure(err)) {
        console.error("Error fetching metrics:", err);
      }
      setMetricsError("Failed to fetch billing metrics. Please check connection.");
    } finally {
      setLoadingMetrics(false);
    }
  }, [api]);

  // Fetch Invoices List
  const fetchInvoices = useCallback(async () => {
    try {
      setLoadingInvoices(true);
      const res = await api.get<{ data: Invoice[] }>("/billing/invoices");
      setInvoices(res.data || []);
      setInvoicesError(null);
    } catch (err) {
      if (!isBenignApiNetworkFailure(err)) {
        console.error("Error fetching invoices:", err);
      }
      setInvoicesError("Failed to fetch invoices list.");
    } finally {
      setLoadingInvoices(false);
    }
  }, [api]);

  const loadAllData = useCallback(() => {
    void fetchMetrics();
    void fetchInvoices();
  }, [fetchMetrics, fetchInvoices]);

  // Poll data periodically
  useEffect(() => {
    loadAllData();
  }, [loadAllData]);
  usePollWhenVisible(loadAllData, 60_000, true);

  // Patient Search Action
  const handlePatientSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!patientSearchQuery.trim()) return;

    try {
      setSearchingPatients(true);
      const res = await api.get<{ data: PatientSearchRow[] }>(`/patients/search/?q=${encodeURIComponent(patientSearchQuery)}`);
      // Adapt response mapping if backend returns differently (some endpoints wrap in pagination/list)
      const list = Array.isArray(res) ? res : res.data || [];
      setPatientSearchResults(list);
      if (list.length === 0) {
        toast.error("No patients found matching query.");
      }
    } catch (err) {
      console.error("Error searching patients:", err);
      toast.error("Patient search failed.");
    } finally {
      setSearchingPatients(false);
    }
  };

  // Add line item
  const handleAddItem = () => {
    setInvoiceItems([
      ...invoiceItems,
      { description: "", quantity: 1, priceGhs: "0.00", serviceType: "SERVICE" }
    ]);
  };

  // Remove line item
  const handleRemoveItem = (index: number) => {
    if (invoiceItems.length === 1) return;
    setInvoiceItems(invoiceItems.filter((_, i) => i !== index));
  };

  // Line item changes
  const handleItemChange = (index: number, key: string, value: string | number) => {
    const updated = [...invoiceItems];
    updated[index] = { ...updated[index], [key]: value };
    setInvoiceItems(updated);
  };

  // Calculate invoice total
  const calculatedInvoiceTotal = useMemo(() => {
    return invoiceItems.reduce((acc, curr) => {
      const price = parseFloat(curr.priceGhs) || 0;
      return acc + (price * curr.quantity);
    }, 0);
  }, [invoiceItems]);

  // Submit new invoice
  const handleCreateInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatient) {
      toast.error("Please select a patient first.");
      return;
    }

    // Validate items
    for (const item of invoiceItems) {
      if (!item.description.trim()) {
        toast.error("Line item descriptions cannot be empty.");
        return;
      }
      const price = parseFloat(item.priceGhs);
      if (isNaN(price) || price < 0) {
        toast.error("Line item price must be a valid positive number.");
        return;
      }
    }

    try {
      setSubmittingInvoice(true);
      
      // Map to cents and backend format
      const itemsPayload = invoiceItems.map(item => ({
        description: item.description,
        quantity: item.quantity,
        unit_price: Math.round(parseFloat(item.priceGhs) * 100), // in cents
        service_type: item.serviceType
      }));

      const payload = {
        patient_id: selectedPatient.patient_id,
        payment_method: paymentMethod,
        notes: invoiceNotes,
        items: itemsPayload
      };

      await api.post("/billing/invoices/new", payload);
      toast.success("Invoice created successfully.");
      
      // Reset form & reload
      setIsCreateInvoiceOpen(false);
      setSelectedPatient(null);
      setPatientSearchQuery("");
      setPatientSearchResults([]);
      setInvoiceNotes("");
      setInvoiceItems([{ description: "General Consultation", quantity: 1, priceGhs: "50.00", serviceType: "CONSULTATION" }]);
      
      loadAllData();
    } catch (err) {
      console.error("Failed to create invoice:", err);
      toast.error("Failed to create invoice. Try again.");
    } finally {
      setSubmittingInvoice(false);
    }
  };

  // Record payment submit
  const handleRecordPaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;

    const amount = parseFloat(paymentAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error("Payment amount must be a positive number.");
      return;
    }

    try {
      setSubmittingPayment(true);
      const payload = {
        amount: amount.toFixed(2),
        payment_reference: paymentReference,
        notes: paymentNotes
      };

      await api.post(`/billing/invoices/${selectedInvoice.id}/pay`, payload);
      toast.success(`Payment of ₵${amount.toFixed(2)} recorded successfully.`);
      
      setIsRecordPaymentOpen(false);
      setPaymentAmount("");
      setPaymentReference("");
      setPaymentNotes("");
      setSelectedInvoice(null);
      
      loadAllData();
    } catch (err) {
      console.error("Failed to record payment:", err);
      toast.error("Payment processing failed.");
    } finally {
      setSubmittingPayment(false);
    }
  };

  // Submit NHIS claim submit
  const handleSubmitNhisSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    if (!nhisMemberId.trim()) {
      toast.error("NHIS Member Card Number is required.");
      return;
    }

    const diagCodes = diagnosisCodes
      .split(",")
      .map(c => c.trim())
      .filter(Boolean);

    if (diagCodes.length === 0) {
      toast.error("At least one ICD-10 diagnosis code is required.");
      return;
    }

    try {
      setSubmittingNhis(true);
      const payload = {
        nhis_member_id: nhisMemberId.trim(),
        diagnosis_codes: diagCodes,
        check_eligibility: checkEligibility
      };

      const res = await api.post<{ claim_reference: string; nhis_status: string }>(
        `/billing/invoices/${selectedInvoice.id}/submit-nhis`,
        payload
      );
      toast.success(`NHIS claim submitted successfully! Ref: ${res.claim_reference || "Queued"}`);
      
      setIsSubmitNhisOpen(false);
      setNhisMemberId("");
      setDiagnosisCodes("A09, B54");
      setSelectedInvoice(null);
      
      loadAllData();
    } catch (err) {
      console.error("NHIS claim submission failed:", err);
      toast.error("Failed to submit NHIS claim.");
    } finally {
      setSubmittingNhis(false);
    }
  };

  // Filter invoices
  const filteredInvoices = useMemo(() => {
    return invoices.filter(inv => {
      const matchStatus = statusFilter === "all" || inv.status === statusFilter;
      const matchSearch = !searchFilter.trim() || 
        inv.patient_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
        inv.id.toLowerCase().includes(searchFilter.toLowerCase());
      return matchStatus && matchSearch;
    });
  }, [invoices, statusFilter, searchFilter]);

  // Open modals handlers
  const openRecordPayment = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    const remainingGhs = (invoice.amount_cents / 100) - invoice.paid_amount;
    setPaymentAmount(remainingGhs.toFixed(2));
    setIsRecordPaymentOpen(true);
  };

  const openSubmitNhis = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    // Find if patient already has nhis_number loaded in registry
    setNhisMemberId("");
    setIsSubmitNhisOpen(true);
  };

  // Format date helper
  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  };

  // Status badges
  const getStatusBadge = (status: Invoice["status"]) => {
    switch (status) {
      case "paid":
        return <Badge variant="success">Paid</Badge>;
      case "partial":
        return <Badge variant="pending" className="bg-amber-100 text-amber-800 border-amber-200">Partial</Badge>;
      case "pending":
        return <Badge variant="pending">Pending</Badge>;
      case "draft":
        return <Badge variant="default" className="bg-slate-100 text-slate-800 border-slate-200">Draft</Badge>;
      case "issued":
        return <Badge variant="default" className="bg-blue-100 text-blue-800 border-blue-200">Issued</Badge>;
      case "cancelled":
        return <Badge variant="critical">Cancelled</Badge>;
    }
  };

  const getPaymentMethodBadge = (method: Invoice["payment_method"]) => {
    switch (method) {
      case "cash":
        return <Badge className="bg-emerald-50 text-emerald-700 border-emerald-100 uppercase text-[10px]">Cash</Badge>;
      case "card":
        return <Badge className="bg-indigo-50 text-indigo-700 border-indigo-100 uppercase text-[10px]">Card</Badge>;
      case "nhis":
        return <Badge className="bg-[#0EAFBE]/10 text-[#0EAFBE] border-[#0EAFBE]/20 uppercase text-[10px]">NHIS</Badge>;
      case "insurance":
        return <Badge className="bg-purple-50 text-purple-700 border-purple-100 uppercase text-[10px]">Insurance</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="hover:scale-[1.01] transition-transform duration-200 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Today&apos;s Revenue</p>
                <p className="text-2xl font-black mt-1 text-emerald-600 dark:text-emerald-400">
                  ₵{metrics?.today.revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                </p>
              </div>
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <DollarSign className="h-5 w-5 text-emerald-500" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-slate-400">
              <span>{metrics?.today.invoices_created ?? 0} Invoices created today</span>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:scale-[1.01] transition-transform duration-200 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Outstanding Bills</p>
                <p className="text-2xl font-black mt-1 text-rose-600 dark:text-rose-400">
                  ₵{metrics?.outstanding.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
                </p>
              </div>
              <div className="p-2 bg-rose-500/10 rounded-lg">
                <AlertCircle className="h-5 w-5 text-rose-500" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-rose-500 font-semibold">
              <span>{metrics?.outstanding.count ?? 0} invoices awaiting payment</span>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:scale-[1.01] transition-transform duration-200 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">NHIS Pending</p>
                <p className="text-2xl font-black mt-1 text-[#0EAFBE]">
                  {metrics?.nhis.pending ?? 0}
                </p>
              </div>
              <div className="p-2 bg-[#0EAFBE]/10 rounded-lg">
                <Clock className="h-5 w-5 text-[#0EAFBE]" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-slate-400">
              <span>Awaiting Ghana NHIA review</span>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:scale-[1.01] transition-transform duration-200 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">NHIS Claims (Month)</p>
                <p className="text-2xl font-black mt-1 text-emerald-600 dark:text-emerald-400">
                  {metrics?.nhis.approved_this_month ?? 0} <span className="text-xs font-normal text-slate-400">App.</span> / <span className="text-rose-500 text-base">{metrics?.nhis.rejected_this_month ?? 0} Rej.</span>
                </p>
              </div>
              <div className="p-2 bg-purple-500/10 rounded-lg">
                <ClipboardCheck className="h-5 w-5 text-purple-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-slate-400">
              <span>Electronic claims processed (30d)</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs Layout */}
      <Tabs defaultValue="overview" onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
          <TabsTrigger value="overview" className="rounded-lg">Revenue Overview</TabsTrigger>
          <TabsTrigger value="registry" className="rounded-lg">Invoices & Payments</TabsTrigger>
          <TabsTrigger value="nhis" className="rounded-lg">NHIS E-Claims Registry</TabsTrigger>
        </TabsList>

        {/* Tab 1: Overview & Trend Chart */}
        <TabsContent value="overview" className="mt-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2 shadow-sm border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <CardHeader>
                <CardTitle className="text-base font-bold flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-emerald-500" />
                  Weekly Revenue Trend
                </CardTitle>
                <CardDescription>Daily hospital collections for the past 7 days</CardDescription>
              </CardHeader>
              <CardContent className="h-[300px]">
                {metrics && metrics.weekly_trend.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={metrics.weekly_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" className="dark:stroke-slate-800" />
                      <XAxis dataKey="date" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `₵${v}`} />
                      <Tooltip formatter={(value) => [`₵${value}`, "Revenue"]} contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} />
                      <Area type="monotone" dataKey="revenue" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorRevenue)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400">
                    No weekly trend data available.
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="shadow-sm border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <CardHeader>
                  <CardTitle className="text-base font-bold">Quick Billing Actions</CardTitle>
                  <CardDescription>Initiate revenue operations</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button className="w-full bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white flex items-center justify-center gap-2 h-11" onClick={() => setIsCreateInvoiceOpen(true)}>
                    <Plus className="h-4 w-4" /> Create New Invoice
                  </Button>
                  <Button variant="outline" className="w-full flex items-center justify-center gap-2 h-11" onClick={() => setActiveTab("registry")}>
                    <CreditCard className="h-4 w-4" /> Record Invoice Payment
                  </Button>
                  <Button variant="outline" className="w-full flex items-center justify-center gap-2 h-11" onClick={() => setActiveTab("nhis")}>
                    <Layers className="h-4 w-4" /> Go to NHIS E-Claims
                  </Button>
                </CardContent>
              </Card>

              <Card className="shadow-sm border-slate-200 dark:border-slate-800 bg-gradient-to-br from-[#0EAFBE] to-[#0A8590] text-white">
                <CardHeader>
                  <CardTitle className="text-white text-base">Ghana GHS Coding Audit</CardTitle>
                  <CardDescription className="text-white/80">Compliance with national billing standards</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>Invoices submitted with ICD-10 diagnostic coding achieve <strong>94% faster claims processing</strong>.</p>
                  <p className="text-xs text-white/70 italic">Please confirm NHIS card numbers are validated prior to consultation claims.</p>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Invoices Registry */}
        <TabsContent value="registry" className="mt-6">
          <Card className="shadow-sm border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
            <CardHeader className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-slate-100 dark:border-slate-800 gap-4">
              <div>
                <CardTitle className="text-lg">Invoices & Billing Registry</CardTitle>
                <CardDescription>View, manage, and process patient payments</CardDescription>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  <Input 
                    placeholder="Search patient name..." 
                    className="pl-9 w-[200px]" 
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                  />
                </div>
                <Select className="w-[150px]" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="all">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="partial">Partially Paid</option>
                  <option value="paid">Paid</option>
                  <option value="cancelled">Cancelled</option>
                </Select>
                <Button className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white flex items-center gap-1" onClick={() => setIsCreateInvoiceOpen(true)}>
                  <Plus className="h-4 w-4" /> Create Invoice
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {loadingInvoices && invoices.length === 0 ? (
                <div className="flex justify-center items-center py-12 text-slate-500">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading invoices...
                </div>
              ) : filteredInvoices.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  No invoices found matching criteria.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50/50 dark:bg-slate-800/20 text-slate-500 font-semibold border-b border-slate-100 dark:border-slate-800 uppercase tracking-wider text-xs">
                        <th className="px-6 py-4 text-left">Invoice No</th>
                        <th className="px-6 py-4 text-left">Patient</th>
                        <th className="px-6 py-4 text-left">Created Date</th>
                        <th className="px-6 py-4 text-left">Amount Billed / Paid</th>
                        <th className="px-6 py-4 text-left">Method</th>
                        <th className="px-6 py-4 text-left">Status</th>
                        <th className="px-6 py-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {filteredInvoices.map((inv) => {
                        const totalGhs = inv.amount_cents / 100;
                        const unpaidGhs = totalGhs - inv.paid_amount;
                        return (
                          <tr key={inv.id} className="hover:bg-slate-50/40 dark:hover:bg-slate-900/40 transition-colors">
                            <td className="px-6 py-4 font-mono font-bold text-[#0EAFBE] truncate max-w-[120px]">
                              {inv.id.substring(0, 8).toUpperCase()}
                            </td>
                            <td className="px-6 py-4">
                              <span className="font-bold text-slate-900 dark:text-slate-100">{inv.patient_name}</span>
                            </td>
                            <td className="px-6 py-4 text-slate-500 whitespace-nowrap">
                              {formatDate(inv.created_at)}
                            </td>
                            <td className="px-6 py-4 font-semibold whitespace-nowrap text-slate-900 dark:text-slate-100">
                              ₵{totalGhs.toFixed(2)} <span className="text-slate-400 text-xs font-normal">/ ₵{inv.paid_amount.toFixed(2)}</span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              {getPaymentMethodBadge(inv.payment_method)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              {getStatusBadge(inv.status)}
                            </td>
                            <td className="px-6 py-4 text-right whitespace-nowrap space-x-1">
                              {inv.status !== "paid" && inv.status !== "cancelled" && (
                                <Button size="sm" variant="primary" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => openRecordPayment(inv)}>
                                  Pay
                                </Button>
                              )}
                              {inv.payment_method === "nhis" && inv.status !== "cancelled" && inv.nhis_claim_status !== "submitted" && inv.nhis_claim_status !== "approved" && (
                                <Button size="sm" variant="outline" className="border-[#0EAFBE] text-[#0EAFBE] hover:bg-[#0EAFBE]/5" onClick={() => openSubmitNhis(inv)}>
                                  NHIS Claim
                                </Button>
                              )}
                              {inv.nhis_claim_status === "submitted" && (
                                <Badge variant="success" className="bg-[#0EAFBE] text-white">NHIS Claim Sent</Badge>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: NHIS Registry */}
        <TabsContent value="nhis" className="mt-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Total Claims Value</p>
                    <p className="text-2xl font-black mt-1">₵{invoices.filter(i => i.payment_method === 'nhis').reduce((acc, curr) => acc + (curr.amount_cents / 100), 0).toFixed(2)}</p>
                  </div>
                  <div className="p-2 bg-[#0EAFBE]/10 rounded-lg">
                    <ClipboardCheck className="h-5 w-5 text-[#0EAFBE]" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Claims Approval Rate</p>
                    <p className="text-2xl font-black mt-1">94.2%</p>
                  </div>
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Pending Review</p>
                    <p className="text-2xl font-black mt-1">{invoices.filter(i => i.payment_method === 'nhis' && i.nhis_claim_status === 'submitted').length}</p>
                  </div>
                  <div className="p-2 bg-amber-500/10 rounded-lg">
                    <Clock className="h-5 w-5 text-amber-500" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Rejections (Month)</p>
                    <p className="text-2xl font-black mt-1">{metrics?.nhis.rejected_this_month ?? 0}</p>
                  </div>
                  <div className="p-2 bg-rose-500/10 rounded-lg">
                    <AlertCircle className="h-5 w-5 text-rose-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800">
              <div>
                <CardTitle className="text-lg">NHIS electronic Health Claims Registry</CardTitle>
                <CardDescription>Ghana Health Insurance Scheme claims tracking for this facility</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50/50 dark:bg-slate-800/20 text-slate-500 font-semibold border-b border-slate-100 dark:border-slate-800 uppercase tracking-wider text-xs">
                      <th className="px-6 py-4 text-left">Claim Ref</th>
                      <th className="px-6 py-4 text-left">Invoice No</th>
                      <th className="px-6 py-4 text-left">Patient Name</th>
                      <th className="px-6 py-4 text-left">Diagnosis (ICD-10)</th>
                      <th className="px-6 py-4 text-left">Claim Value</th>
                      <th className="px-6 py-4 text-left">Claim Status</th>
                      <th className="px-6 py-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {invoices.filter(inv => inv.payment_method === 'nhis').length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center py-12 text-slate-500">
                          No NHIS claims or invoices registered yet.
                        </td>
                      </tr>
                    ) : (
                      invoices.filter(inv => inv.payment_method === 'nhis').map((inv) => {
                        const amount = inv.amount_cents / 100;
                        return (
                          <tr key={inv.id} className="hover:bg-slate-50/40 dark:hover:bg-slate-900/40 transition-colors">
                            <td className="px-6 py-4 font-mono font-bold text-slate-900 dark:text-slate-100">
                              {inv.nhis_claim_reference || "—"}
                            </td>
                            <td className="px-6 py-4 font-mono text-slate-500">
                              {inv.id.substring(0, 8).toUpperCase()}
                            </td>
                            <td className="px-6 py-4">
                              <span className="font-bold text-slate-900 dark:text-slate-100">{inv.patient_name}</span>
                            </td>
                            <td className="px-6 py-4 italic text-slate-500 whitespace-nowrap">
                              {inv.nhis_claim_status ? "ICD-10 Coded" : "Awaiting Code"}
                            </td>
                            <td className="px-6 py-4 font-black">
                              ₵{amount.toFixed(2)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              {inv.nhis_claim_status === "submitted" ? (
                                <Badge className="bg-blue-100 text-blue-800 border-blue-200">Submitted</Badge>
                              ) : inv.nhis_claim_status === "approved" ? (
                                <Badge variant="success">Approved</Badge>
                              ) : inv.nhis_claim_status === "rejected" ? (
                                <Badge variant="critical">Rejected</Badge>
                              ) : (
                                <Badge className="bg-slate-100 text-slate-600 border-slate-200">Draft / Unsubmitted</Badge>
                              )}
                            </td>
                            <td className="px-6 py-4 text-right whitespace-nowrap">
                              {!inv.nhis_claim_status && (
                                <Button size="sm" onClick={() => openSubmitNhis(inv)}>
                                  Submit Claim
                                </Button>
                              )}
                              {inv.nhis_claim_status === "submitted" && (
                                <span className="text-xs text-slate-400 italic">Processing</span>
                              )}
                              {inv.nhis_claim_status === "approved" && (
                                <span className="text-xs text-emerald-600 font-bold">Approved</span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* CREATE INVOICE DIALOG */}
      <Dialog open={isCreateInvoiceOpen} onOpenChange={setIsCreateInvoiceOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent size="lg">
            <DialogClose />
            <DialogHeader>
              <DialogTitle>Create New Patient Invoice</DialogTitle>
              <DialogDescription>Select patient and detail billed line items</DialogDescription>
            </DialogHeader>

            <form onSubmit={handleCreateInvoiceSubmit} className="space-y-4">
              {/* Patient Selector */}
              {!selectedPatient ? (
                <div className="space-y-2 border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-900/45">
                  <label className="text-xs font-bold uppercase text-slate-500">Search Patient</label>
                  <div className="flex gap-2">
                    <Input 
                      placeholder="Search patient by name or Ghana Health ID..."
                      value={patientSearchQuery}
                      onChange={(e) => setPatientSearchQuery(e.target.value)}
                    />
                    <Button type="button" onClick={() => void handlePatientSearch()} disabled={searchingPatients}>
                      {searchingPatients ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    </Button>
                  </div>
                  {/* Results list */}
                  {patientSearchResults.length > 0 && (
                    <div className="max-h-40 overflow-y-auto border border-slate-100 dark:border-slate-800 rounded-lg bg-white dark:bg-slate-900 divide-y divide-slate-100 dark:divide-slate-800 mt-2 text-sm shadow-sm">
                      {patientSearchResults.map(p => (
                        <div key={p.patient_id} className="flex justify-between items-center p-3 hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedPatient(p)}>
                          <div>
                            <p className="font-bold text-slate-900 dark:text-slate-100">{p.full_name}</p>
                            <p className="text-xs text-slate-500">ID: {p.ghana_health_id}</p>
                          </div>
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-between border border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20 dark:border-emerald-800/40 rounded-xl p-4">
                  <div>
                    <span className="text-xs font-bold text-emerald-800 uppercase dark:text-emerald-400">Selected Patient</span>
                    <h4 className="text-lg font-extrabold text-slate-900 dark:text-slate-100">{selectedPatient.full_name}</h4>
                    <p className="text-xs text-slate-500">Health ID: {selectedPatient.ghana_health_id}</p>
                    {selectedPatient.nhis_number && (
                      <p className="text-xs text-slate-500 font-semibold mt-1 text-[#0EAFBE]">NHIS: {selectedPatient.nhis_number}</p>
                    )}
                  </div>
                  <Button type="button" variant="outline" size="sm" className="text-rose-600 border-rose-200 hover:bg-rose-50" onClick={() => { setSelectedPatient(null); setPatientSearchResults([]); }}>
                    Change
                  </Button>
                </div>
              )}

              {/* Payment Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Select label="Payment Method" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as "cash" | "card" | "nhis" | "insurance")}>
                  <option value="cash">Cash Collection</option>
                  <option value="card">Credit / Debit Card</option>
                  <option value="nhis">National Health Insurance (NHIS)</option>
                  <option value="insurance">Private Health Insurance</option>
                </Select>
                <div className="flex flex-col justify-end">
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">Invoice Total</label>
                  <div className="h-11 border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center px-3 rounded-lg text-lg font-black text-slate-900 dark:text-slate-100">
                    ₵{calculatedInvoiceTotal.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Invoice Items Section */}
              <div className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-bold uppercase tracking-wider text-slate-600">Line Items</h4>
                  <Button type="button" size="sm" variant="outline" className="flex items-center gap-1 border-slate-200" onClick={handleAddItem}>
                    <Plus className="h-3.5 w-3.5" /> Add Item
                  </Button>
                </div>

                <div className="space-y-3 max-h-48 overflow-y-auto">
                  {invoiceItems.map((item, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <div className="flex-[3]">
                        <Input 
                          placeholder="Item description..." 
                          value={item.description}
                          onChange={(e) => handleItemChange(idx, "description", e.target.value)}
                        />
                      </div>
                      <div className="flex-[1]">
                        <Input 
                          type="number"
                          placeholder="Qty" 
                          value={item.quantity}
                          onChange={(e) => handleItemChange(idx, "quantity", parseInt(e.target.value) || 1)}
                        />
                      </div>
                      <div className="flex-[2]">
                        <Input 
                          placeholder="Price (₵)" 
                          value={item.priceGhs}
                          onChange={(e) => handleItemChange(idx, "priceGhs", e.target.value)}
                        />
                      </div>
                      <div className="flex-[2]">
                        <Select value={item.serviceType} onChange={(e) => handleItemChange(idx, "serviceType", e.target.value)}>
                          <option value="CONSULTATION">Consult</option>
                          <option value="MEDICINE">Drug</option>
                          <option value="LAB">Lab test</option>
                          <option value="WARD">Ward/Bed</option>
                          <option value="SERVICE">Service</option>
                        </Select>
                      </div>
                      {invoiceItems.length > 1 && (
                        <Button type="button" variant="ghost" size="sm" className="text-rose-500 hover:text-rose-700" onClick={() => handleRemoveItem(idx)}>
                          <XCircle className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <Textarea 
                label="Invoice Notes"
                placeholder="Optional billing notes..."
                value={invoiceNotes}
                onChange={(e) => setInvoiceNotes(e.target.value)}
              />

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsCreateInvoiceOpen(false)}>Cancel</Button>
                <Button type="submit" className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white" disabled={submittingInvoice || !selectedPatient}>
                  {submittingInvoice ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Create & Issue Invoice
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </DialogPortal>
      </Dialog>

      {/* RECORD PAYMENT DIALOG */}
      <Dialog open={isRecordPaymentOpen} onOpenChange={setIsRecordPaymentOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogClose />
            <DialogHeader>
              <DialogTitle>Record Invoice Payment</DialogTitle>
              <DialogDescription>Process incoming collection for invoice</DialogDescription>
            </DialogHeader>

            {selectedInvoice && (
              <form onSubmit={handleRecordPaymentSubmit} className="space-y-4">
                <div className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-900/50 text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Patient:</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">{selectedInvoice.patient_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Bill:</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">₵{(selectedInvoice.amount_cents / 100).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Amount Paid So Far:</span>
                    <span className="font-bold text-emerald-600">₵{selectedInvoice.paid_amount.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 dark:border-slate-800 pt-2 mt-2">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Remaining Balance:</span>
                    <span className="font-black text-rose-600">₵{((selectedInvoice.amount_cents / 100) - selectedInvoice.paid_amount).toFixed(2)}</span>
                  </div>
                </div>

                <Input 
                  label="Collection Amount (₵)" 
                  placeholder="Enter GHS amount..."
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(e.target.value)}
                  required
                />

                <Input 
                  label="Payment Reference" 
                  placeholder="Bank reference, cash receipt ID, card auth code..."
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                />

                <Textarea 
                  label="Payment Notes"
                  placeholder="Payment metadata/notes..."
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                />

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsRecordPaymentOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-emerald-600 hover:bg-emerald-700 text-white" disabled={submittingPayment}>
                    {submittingPayment ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Confirm Receipt & Pay
                  </Button>
                </DialogFooter>
              </form>
            )}
          </DialogContent>
        </DialogPortal>
      </Dialog>

      {/* SUBMIT NHIS CLAIM DIALOG */}
      <Dialog open={isSubmitNhisOpen} onOpenChange={setIsSubmitNhisOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogClose />
            <DialogHeader>
              <DialogTitle>Submit NHIS Electronic Health Claim</DialogTitle>
              <DialogDescription>Submit e-claim to the Ghana National Health Insurance Authority (NHIA) gateway</DialogDescription>
            </DialogHeader>

            {selectedInvoice && (
              <form onSubmit={handleSubmitNhisSubmit} className="space-y-4">
                <div className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-900/50 text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Patient:</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">{selectedInvoice.patient_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Claim Total Value:</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">₵{(selectedInvoice.amount_cents / 100).toFixed(2)}</span>
                  </div>
                </div>

                <Input 
                  label="NHIS Member Card Number" 
                  placeholder="Enter 8-digit NHIS number..."
                  value={nhisMemberId}
                  onChange={(e) => setNhisMemberId(e.target.value)}
                  required
                />

                <Input 
                  label="ICD-10 Diagnosis Codes" 
                  placeholder="e.g. A09, B54, I10..."
                  value={diagnosisCodes}
                  onChange={(e) => setDiagnosisCodes(e.target.value)}
                  required
                />
                <p className="text-[10px] text-slate-400 italic -mt-2">
                  * Comma-separated list. Codes must be valid ICD-10 diagnostic codes for processing.
                </p>

                <div className="flex items-center gap-2 border border-slate-200 dark:border-slate-800 rounded-lg p-3">
                  <input 
                    type="checkbox" 
                    id="check_eligibility" 
                    className="h-4 w-4 text-[#0EAFBE] border-slate-300 rounded" 
                    checked={checkEligibility}
                    onChange={(e) => setCheckEligibility(e.target.checked)}
                  />
                  <label htmlFor="check_eligibility" className="text-xs font-semibold text-slate-600 select-none cursor-pointer">
                    Verify card validity with NHIA registry prior to claim submission
                  </label>
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsSubmitNhisOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white" disabled={submittingNhis}>
                    {submittingNhis ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Transmit E-Claim
                  </Button>
                </DialogFooter>
              </form>
            )}
          </DialogContent>
        </DialogPortal>
      </Dialog>
    </div>
  );
}
