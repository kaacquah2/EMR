"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useReferrals } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ReferralListItem, ReferralStatus } from "@/lib/types";
import type { BadgeVariant } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { 
  ArrowUpRight, 
  ArrowDownLeft,
  CheckCircle2,
  Clock,
  XCircle,
  FileSearch,
} from "lucide-react";

const statusVariant: Record<ReferralStatus, BadgeVariant> = {
  PENDING: "pending",
  ACCEPTED: "active",
  REJECTED: "critical",
  COMPLETED: "default",
  CANCELLED: "inactive",
};

export default function ReferralsPage() {
  const router = useRouter();
  const { incoming, outgoing, summary, loading, error, fetchMine, updateStatus } = useReferrals();
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    fetchMine();
  }, [fetchMine]);

  const handleStatus = async (referralId: string, status: ReferralStatus) => {
    setUpdatingId(referralId);
    try {
      await updateStatus(referralId, status);
      await fetchMine();
    } finally {
      setUpdatingId(null);
    }
  };

  const SummaryCard = ({ title, count, icon: Icon, color }: { title: string; count: number; icon: React.ElementType; color: string }) => (
    <Card className="p-4 flex items-center justify-between shadow-sm border-slate-100 dark:border-slate-800">
      <div>
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{title}</p>
        <p className="text-2xl font-bold font-sora mt-1 text-slate-900 dark:text-white">{count}</p>
      </div>
      <div className={`h-12 w-12 rounded-full flex items-center justify-center ${color}`}>
        <Icon className="h-6 w-6" />
      </div>
    </Card>
  );

  const ReferralTable = ({ data, direction }: { data: ReferralListItem[]; direction: "incoming" | "outgoing" }) => (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Patient</th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
              {direction === 'incoming' ? 'From Facility' : 'To Facility'}
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Reason</th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Date</th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {data.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
              <td className="px-6 py-4">
                <div className="flex flex-col">
                  <span className="font-semibold text-slate-900 dark:text-white">{r.patient.name}</span>
                  <span className="text-xs text-slate-500 font-mono">{r.patient.ghana_health_id || r.patient.id.slice(0,8)}</span>
                </div>
              </td>
              <td className="px-6 py-4 font-medium text-slate-700 dark:text-slate-300">
                {direction === 'incoming' ? r.from_facility.name : r.to_facility.name}
              </td>
              <td className="px-6 py-4">
                <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-1 max-w-[200px]">
                  {r.reason}
                </p>
              </td>
              <td className="px-6 py-4">
                <Badge variant={statusVariant[r.status]} className="font-medium">
                  {r.status}
                </Badge>
              </td>
              <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-500">
                {new Date(r.created_at).toLocaleDateString()}
              </td>
              <td className="px-6 py-4 text-right space-x-2">
                {direction === 'outgoing' && r.status === "PENDING" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                    disabled={updatingId === r.id}
                    onClick={() => handleStatus(r.id, "CANCELLED")}
                  >
                    Cancel
                  </Button>
                )}
                {direction === 'incoming' && r.status === "PENDING" && (
                  <>
                    <Button
                      size="sm"
                      className="bg-[#0B8A96] hover:bg-[#0B8A96]/90"
                      disabled={updatingId === r.id}
                      onClick={() => handleStatus(r.id, "ACCEPTED")}
                    >
                      {updatingId === r.id ? "..." : "Accept"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      disabled={updatingId === r.id}
                      onClick={() => handleStatus(r.id, "REJECTED")}
                    >
                      Reject
                    </Button>
                  </>
                )}
                {direction === 'incoming' && r.status === "ACCEPTED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-[#0B8A96] text-[#0B8A96] hover:bg-[#0B8A96]/5"
                    disabled={updatingId === r.id}
                    onClick={() => handleStatus(r.id, "COMPLETED")}
                  >
                    Mark Seen
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push(`/cross-facility-records/${r.patient.id}`)}
                  className="text-slate-500 hover:text-[#0B8A96]"
                >
                  <FileSearch className="h-4 w-4 mr-1" /> Records
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-sora text-3xl font-bold text-slate-900 dark:text-white">
            Patient Referrals
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Track and manage incoming and outgoing patient transfers.
          </p>
        </div>
        <Button onClick={() => router.push("/cross-facility-records")} className="bg-[#0B8A96] hover:bg-[#0B8A96]/90 shadow-md">
          <ArrowUpRight className="mr-2 h-4 w-4" /> New Referral
        </Button>
      </div>

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard 
            title="Pending Actions" 
            count={summary.pending} 
            icon={Clock} 
            color="bg-amber-100 text-amber-600 dark:bg-amber-950/30 dark:text-amber-500" 
          />
          <SummaryCard 
            title="Accepted" 
            count={summary.accepted} 
            icon={CheckCircle2} 
            color="bg-emerald-100 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-500" 
          />
          <SummaryCard 
            title="Total Incoming" 
            count={summary.incoming} 
            icon={ArrowDownLeft} 
            color="bg-blue-100 text-blue-600 dark:bg-blue-950/30 dark:text-blue-500" 
          />
          <SummaryCard 
            title="Total Outgoing" 
            count={summary.outgoing} 
            icon={ArrowUpRight} 
            color="bg-purple-100 text-purple-600 dark:bg-purple-950/30 dark:text-purple-500" 
          />
        </div>
      )}

      {error && (
        <Card className="p-4 border-red-200 bg-red-50 text-red-700 dark:bg-red-950/20 dark:border-red-900/30 dark:text-red-400">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5" />
            <p className="font-medium">{error}</p>
          </div>
        </Card>
      )}

      <Card className="overflow-hidden border-slate-200 dark:border-slate-800 shadow-xl bg-white dark:bg-slate-950">
        <Tabs defaultValue="incoming" className="w-full">
          <div className="px-6 pt-4 border-b border-slate-100 dark:border-slate-800">
            <TabsList className="bg-slate-100/50 dark:bg-slate-900 p-1">
              <TabsTrigger value="incoming" className="data-[state=active]:bg-white dark:data-[state=active]:bg-slate-800 data-[state=active]:shadow-sm">
                <ArrowDownLeft className="mr-2 h-4 w-4" /> Incoming Referrals
              </TabsTrigger>
              <TabsTrigger value="outgoing" className="data-[state=active]:bg-white dark:data-[state=active]:bg-slate-800 data-[state=active]:shadow-sm">
                <ArrowUpRight className="mr-2 h-4 w-4" /> Outgoing Requests
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="incoming" className="m-0">
            {loading ? (
              <div className="py-20 text-center text-slate-500">Loading incoming referrals...</div>
            ) : incoming.length === 0 ? (
              <EmptyState
                icon={<ArrowDownLeft className="h-12 w-12 text-slate-200" />}
                title="No incoming referrals"
                description="Other facilities haven't sent any patients to your hospital yet."
              />
            ) : (
              <ReferralTable data={incoming} direction="incoming" />
            )}
          </TabsContent>

          <TabsContent value="outgoing" className="m-0">
            {loading ? (
              <div className="py-20 text-center text-slate-500">Loading outgoing referrals...</div>
            ) : outgoing.length === 0 ? (
              <EmptyState
                icon={<ArrowUpRight className="h-12 w-12 text-slate-200" />}
                title="No outgoing referrals"
                description="You haven't referred any patients to other hospitals yet."
                action={
                  <Button variant="outline" className="mt-4" onClick={() => router.push("/cross-facility-records")}>
                    Search Registry to Refer
                  </Button>
                }
              />
            ) : (
              <ReferralTable data={outgoing} direction="outgoing" />
            )}
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
}
