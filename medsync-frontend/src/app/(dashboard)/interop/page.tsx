"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useAccessiblePatients, useReferrals, useConsents } from "@/hooks/use-interop";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/ui/stat-card";
import { 
  Users, 
  ArrowUpRight, 
  ArrowDownLeft, 
  ShieldCheck, 
  ExternalLink, 
  Search,
  Activity,
  ChevronRight
} from "lucide-react";

function formatActivityDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function InteropHubPage() {
  const { user } = useAuth();
  const { patients, fetch: fetchPatients, loading: loadingPatients } = useAccessiblePatients();
  const { incoming, outgoing, fetchMine: fetchReferrals, loading: loadingReferrals } = useReferrals();
  const { list: consents, fetchList: fetchConsents, loading: loadingConsents } = useConsents();

  useEffect(() => {
    if (user) {
      fetchPatients();
      fetchReferrals();
      fetchConsents();
    }
  }, [user, fetchPatients, fetchReferrals, fetchConsents]);

  const recentActivity = [
    ...incoming.map(r => ({ ...r, type: 'incoming_referral', date: r.created_at })),
    ...outgoing.map(r => ({ ...r, type: 'outgoing_referral', date: r.created_at })),
    ...consents.map(c => ({ ...c, type: 'consent', date: c.created_at }))
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).slice(0, 5);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight font-sora">Inter-Hospital Interoperability Hub</h1>
        <p className="text-muted-foreground">
          Centralized management for cross-facility patient records, referrals, and clinical consents.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Accessible Patients"
          value={patients.length}
          subtitle="Cross-facility records"
          accent="teal"
        />
        <StatCard
          label="Incoming Referrals"
          value={incoming.filter(r => r.status === 'PENDING').length}
          subtitle="Pending your review"
          accent="navy"
        />
        <StatCard
          label="Outgoing Referrals"
          value={outgoing.length}
          subtitle="Tracked requests"
          accent="amber"
        />
        <StatCard
          label="Active Consents"
          value={consents.filter(c => c.is_active).length}
          subtitle="Authorized access"
          accent="green"
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Accessible Patients Section */}
        <Card className="flex flex-col">
          <div className="p-6 flex flex-row items-center justify-between space-y-0">
            <div>
              <h2 className="text-xl font-semibold font-sora">Cross-Facility Access</h2>
              <p className="text-sm text-muted-foreground">Patients you can currently view from other hospitals</p>
            </div>
            <Link href="/patients">
              <Button variant="ghost" size="sm" className="gap-1">
                Registry <Search className="h-4 w-4" />
              </Button>
            </Link>
          </div>
          <div className="px-6 pb-6 flex-1">
            {loadingPatients ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : patients.length > 0 ? (
              <div className="space-y-4">
                {patients.slice(0, 5).map((patient) => (
                  <div key={patient.global_patient_id} className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-muted/50 transition-colors">
                    <div>
                      <p className="font-medium">{patient.full_name}</p>
                      <p className="text-xs text-muted-foreground">{patient.ghana_health_id || 'No GID'}</p>
                    </div>
                    <Link href={`/patients/${patient.global_patient_id}?interop=true`}>
                      <Button size="sm" variant="outline" className="gap-2">
                        View Records <ExternalLink className="h-3 w-3" />
                      </Button>
                    </Link>
                  </div>
                ))}
                {patients.length > 5 && (
                  <Link href="/patients?filter=accessible">
                    <Button variant="link" className="w-full text-muted-foreground">
                      View all {patients.length} patients
                    </Button>
                  </Link>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-32 text-center">
                <Users className="h-8 w-8 text-muted-foreground mb-2 opacity-20" />
                <p className="text-sm text-muted-foreground">No cross-facility records found.</p>
                <Link href="/patients" className="mt-2">
                  <Button variant="link" size="sm">Search Registry</Button>
                </Link>
              </div>
            )}
          </div>
        </Card>

        {/* Recent Activity Section */}
        <Card className="flex flex-col">
          <div className="p-6 flex flex-row items-center justify-between space-y-0">
            <div>
              <h2 className="text-xl font-semibold font-sora">Recent Interop Activity</h2>
              <p className="text-sm text-muted-foreground">Latest referrals and consent changes</p>
            </div>
            <Link href="/referrals">
              <Button variant="ghost" size="sm" className="gap-1">
                History <Activity className="h-4 w-4" />
              </Button>
            </Link>
          </div>
          <div className="px-6 pb-6 flex-1">
            {loadingReferrals || loadingConsents ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : recentActivity.length > 0 ? (
              <div className="space-y-4">
                {recentActivity.map((activity, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-border">
                    <div className={`mt-1 p-1.5 rounded-full ${
                      activity.type === 'incoming_referral' ? 'bg-blue-100 text-blue-600' : 
                      activity.type === 'outgoing_referral' ? 'bg-amber-100 text-amber-600' :
                      'bg-green-100 text-green-600'
                    }`}>
                      {activity.type === 'incoming_referral' ? <ArrowDownLeft className="h-4 w-4" /> : 
                       activity.type === 'outgoing_referral' ? <ArrowUpRight className="h-4 w-4" /> :
                       <ShieldCheck className="h-4 w-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium truncate">
                          {activity.type === 'consent' ? 'Consent Updated' : 
                           activity.type === 'incoming_referral' ? 'Referral Received' : 'Referral Sent'}
                        </p>
                        <span className="text-[10px] text-muted-foreground uppercase font-semibold">
                          {formatActivityDate(activity.date)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {activity.type === 'consent' ? 
                          `Access granted to ${(activity as { granted_to_facility_name?: string }).granted_to_facility_name || "Facility"}` :
                          activity.type === 'incoming_referral' ? 
                          `From ${(activity as { from_facility_name?: string }).from_facility_name || "Facility"}` : 
                          `To ${(activity as { to_facility_name?: string }).to_facility_name || "Facility"}`}
                      </p>
                      {(activity as { status?: string }).status && (
                        <Badge variant="outline" className="mt-1 text-[10px] px-1.5 py-0">
                          {(activity as { status?: string }).status}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-32 text-center">
                <Activity className="h-8 w-8 text-muted-foreground mb-2 opacity-20" />
                <p className="text-sm text-muted-foreground">No recent activity.</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Quick Actions Row */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4 flex items-center gap-4 hover:bg-muted/50 transition-colors cursor-pointer group">
          <div className="bg-primary/10 p-3 rounded-xl group-hover:bg-primary/20 transition-colors">
            <Search className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold">Global Search</h3>
            <p className="text-xs text-muted-foreground">Find patients nationwide</p>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </Card>
        
        <Link href="/referrals?action=new" className="block">
          <Card className="p-4 flex items-center gap-4 hover:bg-muted/50 transition-colors cursor-pointer group h-full">
            <div className="bg-amber-100 p-3 rounded-xl group-hover:bg-amber-200 transition-colors text-amber-600">
              <ArrowUpRight className="h-6 w-6" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold">Initiate Referral</h3>
              <p className="text-xs text-muted-foreground">Refer patient to specialist</p>
            </div>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </Card>
        </Link>

        <Card className="p-4 flex items-center gap-4 hover:bg-muted/50 transition-colors cursor-pointer group">
          <div className="bg-green-100 p-3 rounded-xl group-hover:bg-green-200 transition-colors text-green-600">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold">Manage Consents</h3>
            <p className="text-xs text-muted-foreground">Review patient permissions</p>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </Card>
      </div>
    </div>
  );
}
