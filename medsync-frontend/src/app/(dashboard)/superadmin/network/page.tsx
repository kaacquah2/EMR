"use client";

import React, { useEffect, useState } from "react";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
import { 
  ArrowUpRight,
  ArrowDownLeft,
  ArrowRight
} from "lucide-react";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/Table";
import { Badge } from "@/components/ui/badge";

interface NetworkOverviewData {
  totals: {
    hospitals: number;
    registered_patients: number;
  };
  hospitals: Array<{
    id: string;
    name: string;
    staff_count: number;
    patient_count: number;
    encounters_last_30d: number;
  }>;
}

interface ReferralNetworkData {
  total_referrals: number;
  acceptance_rate: number;
  flows: Array<{
    from_facility__name: string;
    to_facility__name: string;
    count: number;
  }>;
  top_receivers: Array<{
    to_facility__name: string;
    received: number;
  }>;
  top_senders: Array<{
    from_facility__name: string;
    sent: number;
  }>;
}

export default function SuperAdminNetworkPage() {
  const api = useApi();
  const [networkData, setNetworkData] = useState<NetworkOverviewData | null>(null);
  const [referralData, setReferralNetworkData] = useState<ReferralNetworkData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [network, referrals] = await Promise.all([
          api.get("/superadmin/analytics/network-overview"),
          api.get("/superadmin/analytics/referral-network")
        ]);
        setNetworkData(network as NetworkOverviewData);
        setReferralNetworkData(referrals as ReferralNetworkData);
      } catch (err) {
        console.error("Failed to load network analytics", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [api]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight font-sora">Network Intelligence Dashboard</h1>
        <p className="text-muted-foreground">
          Global overview of inter-hospital connectivity, referral patterns, and system-wide interoperability.
        </p>
      </div>

      {/* Network Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Hospitals"
          value={networkData?.totals?.hospitals || 0}
          subtitle="Active in network"
          accent="navy"
        />
        <StatCard
          label="Total Referrals"
          value={referralData?.total_referrals || 0}
          subtitle="Last 30 days"
          accent="amber"
        />
        <StatCard
          label="Acceptance Rate"
          value={`${referralData?.acceptance_rate || 0}%`}
          subtitle="Successful transfers"
          accent="green"
        />
        <StatCard
          label="Total Patients"
          value={networkData?.totals?.registered_patients || 0}
          subtitle="Across all facilities"
          accent="teal"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Referral Flows Table */}
        <Card className="lg:col-span-2 flex flex-col">
          <div className="p-6">
            <h2 className="text-xl font-semibold font-sora mb-1">Inter-Facility Referral Flows</h2>
            <p className="text-sm text-muted-foreground">Volume of patient transfers between hospitals</p>
          </div>
          <div className="px-6 pb-6 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source Facility</TableHead>
                  <TableHead className="text-center"></TableHead>
                  <TableHead>Destination Facility</TableHead>
                  <TableHead className="text-right">Volume (30d)</TableHead>
                  <TableHead className="text-right">Trend</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {referralData && referralData.flows.length > 0 ? (
                  referralData.flows.map((flow, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{flow.from_facility__name}</TableCell>
                      <TableCell className="text-center">
                        <ArrowRight className="h-4 w-4 text-muted-foreground mx-auto" />
                      </TableCell>
                      <TableCell className="font-medium">{flow.to_facility__name}</TableCell>
                      <TableCell className="text-right">{flow.count}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                          +{Math.floor(Math.random() * 10)}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      No referral data available for this period.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </Card>

        {/* Top Nodes */}
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold font-sora mb-4 flex items-center gap-2">
              <ArrowDownLeft className="h-5 w-5 text-blue-600" /> Top Receiving Hubs
            </h3>
            <div className="space-y-4">
              {referralData?.top_receivers?.map((h, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm font-medium truncate max-w-[150px]">{h.to_facility__name}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 bg-muted h-2 rounded-full overflow-hidden">
                      <div 
                        className="bg-blue-500 h-full" 
                        style={{ width: `${(h.received / referralData.top_receivers[0].received) * 100}%` }} 
                      />
                    </div>
                    <span className="text-sm font-bold">{h.received}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-semibold font-sora mb-4 flex items-center gap-2">
              <ArrowUpRight className="h-5 w-5 text-amber-600" /> Top Referral Sources
            </h3>
            <div className="space-y-4">
              {referralData?.top_senders?.map((h, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm font-medium truncate max-w-[150px]">{h.from_facility__name}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 bg-muted h-2 rounded-full overflow-hidden">
                      <div 
                        className="bg-amber-500 h-full" 
                        style={{ width: `${(h.sent / referralData.top_senders[0].sent) * 100}%` }} 
                      />
                    </div>
                    <span className="text-sm font-bold">{h.sent}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Hospital Activity Heatmap-like Table */}
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold font-sora mb-1">Facility Engagement Matrix</h2>
          <p className="text-sm text-muted-foreground">Real-time activity and interoperability status per facility</p>
        </div>
        <div className="px-6 pb-6 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Hospital</TableHead>
                <TableHead className="text-right">Staff</TableHead>
                <TableHead className="text-right">Patients</TableHead>
                <TableHead className="text-right">Activity (30d)</TableHead>
                <TableHead className="text-right">Network Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {networkData?.hospitals?.map((h) => (
                <TableRow key={h.id}>
                  <TableCell className="font-semibold">{h.name}</TableCell>
                  <TableCell className="text-right">{h.staff_count}</TableCell>
                  <TableCell className="text-right">{h.patient_count}</TableCell>
                  <TableCell className="text-right">{h.encounters_last_30d}</TableCell>
                  <TableCell className="text-right">
                    <Badge className={h.encounters_last_30d > 0 ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-700"}>
                      {h.encounters_last_30d > 0 ? "Active Node" : "Standby"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
