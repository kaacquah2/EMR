"use client";

import React, { useState } from "react";
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
  GanttChart
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell 
} from "recharts";

interface Claim {
  id: string;
  patient_name: string;
  nhis_number: string;
  date: string;
  amount: number;
  status: "pending" | "submitted" | "approved" | "rejected";
  diagnosis: string;
  error_code?: string;
}

const MOCK_CLAIMS: Claim[] = [
  { id: "NH-001", patient_name: "Kojo Mensah", nhis_number: "88234412", date: "2024-05-10", amount: 450.00, status: "pending", diagnosis: "Malaria, unspecified" },
  { id: "NH-002", patient_name: "Abena Mansa", nhis_number: "77211099", date: "2024-05-11", amount: 1200.50, status: "submitted", diagnosis: "Typhoid Fever" },
  { id: "NH-003", patient_name: "Kwame Appiah", nhis_number: "99122334", date: "2024-05-12", amount: 320.00, status: "approved", diagnosis: "Acute URI" },
  { id: "NH-004", patient_name: "Esi Boateng", nhis_number: "44556677", date: "2024-05-13", amount: 890.00, status: "rejected", diagnosis: "HTN Crisis", error_code: "E-104: Invalid Code" },
  { id: "NH-005", patient_name: "Yaw Sarfo", nhis_number: "11223344", date: "2024-05-14", amount: 150.00, status: "pending", diagnosis: "Gastritis" },
];

const DATA_SUMMARY = [
  { name: "Approved", value: 45000, color: "#10b981" },
  { name: "Pending", value: 12000, color: "#f59e0b" },
  { name: "Rejected", value: 3500, color: "#ef4444" },
];

/**
 * NHIS Claims Dashboard
 * 
 * Specialized for Ghanaian health financing compliance.
 */
export function NhisClaimsDashboard() {
  const [activeTab, setActiveTab] = useState("all");

  const filteredClaims = activeTab === "all" 
    ? MOCK_CLAIMS 
    : MOCK_CLAIMS.filter(c => c.status === activeTab);

  const getStatusBadge = (status: Claim["status"]) => {
    switch (status) {
      case "approved": return <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> Approved</Badge>;
      case "pending": return <Badge variant="pending"><Clock className="h-3 w-3 mr-1" /> Pending</Badge>;
      case "submitted": return <Badge variant="default" className="bg-blue-500 text-white hover:bg-blue-600"><TrendingUp className="h-3 w-3 mr-1" /> Submitted</Badge>;
      case "rejected": return <Badge variant="critical"><XCircle className="h-3 w-3 mr-1" /> Rejected</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* KPI Header */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Total Claims</p>
                <p className="text-2xl font-black mt-1">₵60,500</p>
              </div>
              <div className="p-2 bg-[#0EAFBE]/10 rounded-lg">
                <ClipboardCheck className="h-5 w-5 text-[#0EAFBE]" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-emerald-500 font-bold">
              <TrendingUp className="h-3 w-3" />
              <span>+12.5% vs last month</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Approval Rate</p>
                <p className="text-2xl font-black mt-1">94.2%</p>
              </div>
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-emerald-500 font-bold">
              <span>Optimized ICD-10 coding</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Pending Review</p>
                <p className="text-2xl font-black mt-1">24</p>
              </div>
              <div className="p-2 bg-amber-500/10 rounded-lg">
                <Clock className="h-5 w-5 text-amber-500" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-slate-400 italic">
              <span>Avg. turnaround: 4.2 days</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Rejection Loss</p>
                <p className="text-2xl font-black mt-1">₵3,500</p>
              </div>
              <div className="p-2 bg-rose-500/10 rounded-lg">
                <AlertCircle className="h-5 w-5 text-rose-500" />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs text-rose-500 font-bold underline cursor-pointer">
              <span>View error patterns</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Claims Table */}
        <Card className="lg:col-span-2 border-slate-200 dark:border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800">
            <div>
              <CardTitle className="text-lg">NHIS Claims Registry</CardTitle>
              <CardDescription>Manage and track electronic health claims.</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="flex items-center gap-2">
                <Filter className="h-4 w-4" /> Filter
              </Button>
              <Button size="sm" className="bg-[#0EAFBE] hover:bg-[#0E8F9B] text-white flex items-center gap-2">
                <Download className="h-4 w-4" /> Export XML
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Tabs defaultValue="all" onValueChange={setActiveTab} className="w-full">
              <TabsList className="w-full rounded-none border-b border-slate-100 dark:border-slate-800 bg-transparent h-12">
                <TabsTrigger value="all" className="flex-1 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#0EAFBE]">All Claims</TabsTrigger>
                <TabsTrigger value="pending" className="flex-1 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#0EAFBE]">Pending</TabsTrigger>
                <TabsTrigger value="submitted" className="flex-1 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#0EAFBE]">Submitted</TabsTrigger>
                <TabsTrigger value="rejected" className="flex-1 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[#0EAFBE]">Rejected</TabsTrigger>
              </TabsList>
              
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                      <th className="px-6 py-4 text-left">Claim ID</th>
                      <th className="px-6 py-4 text-left">Patient</th>
                      <th className="px-6 py-4 text-left">Diagnosis</th>
                      <th className="px-6 py-4 text-left">Value</th>
                      <th className="px-6 py-4 text-left">Status</th>
                      <th className="px-6 py-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredClaims.map((claim) => (
                      <tr key={claim.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-[#0EAFBE]">{claim.id}</td>
                        <td className="px-6 py-4">
                          <div className="flex flex-col">
                            <span className="text-sm font-bold text-slate-900 dark:text-white">{claim.patient_name}</span>
                            <span className="text-xs text-slate-500">NHIS: {claim.nhis_number}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm text-slate-600 dark:text-slate-400 italic line-clamp-1">{claim.diagnosis}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap font-black text-sm">₵{claim.amount.toFixed(2)}</td>
                        <td className="px-6 py-4">{getStatusBadge(claim.status)}</td>
                        <td className="px-6 py-4 text-right">
                          <Button size="sm" variant="ghost">
                            <FileSearch className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Tabs>
          </CardContent>
        </Card>

        {/* Analytics Sidebar */}
        <div className="space-y-6">
          <Card className="border-slate-200 dark:border-slate-800">
            <CardHeader>
              <CardTitle className="text-sm font-bold uppercase tracking-widest text-slate-500">Value Distribution</CardTitle>
            </CardHeader>
            <CardContent className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={DATA_SUMMARY} layout="vertical" margin={{ left: 10, right: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" width={80} axisLine={false} tickLine={false} fontSize={12} />
                  <Tooltip 
                    cursor={{fill: 'transparent'}}
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={24}>
                    {DATA_SUMMARY.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="bg-[#0EAFBE] text-white border-none shadow-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GanttChart className="h-5 w-5" />
                Compliance Score
              </CardTitle>
              <CardDescription className="text-white/80">Hospital coding accuracy index.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-end justify-between">
                  <span className="text-4xl font-black">98.1%</span>
                  <Badge variant="default" className="bg-white text-[#0EAFBE] hover:bg-white/90">EXCELLENT</Badge>
                </div>
                <div className="h-2 bg-white/20 rounded-full overflow-hidden">
                  <div className="h-full bg-white w-[98.1%]" />
                </div>
                <p className="text-xs text-white/70 italic">
                  * Based on GHS Standard Quality Metrics for NHIS providers.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
