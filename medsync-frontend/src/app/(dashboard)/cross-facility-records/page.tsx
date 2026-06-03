"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAccessiblePatients, useGlobalPatientSearch } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { 
  Users, 
  Search, 
  FileText, 
  ShieldAlert, 
  History, 
  ChevronRight,
  UserPlus
} from "lucide-react";

export default function CrossFacilityRecordsPage() {
  const router = useRouter();
  const { patients, loading, fetch } = useAccessiblePatients();
  const { results: searchResults, loading: searchLoading, search } = useGlobalPatientSearch();
  const [searchQuery, setSearchQuery] = React.useState("");

  useEffect(() => {
    fetch();
  }, [fetch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    search(searchQuery);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-sora text-3xl font-bold text-slate-900 dark:text-white">
            Cross-Facility Records
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Access and manage patient health records from across the MedSync network.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => router.push("/patients")}>
            <Users className="mr-2 h-4 w-4" /> Local Patients
          </Button>
          <Button onClick={() => router.push("/patients/register")}>
            <UserPlus className="mr-2 h-4 w-4" /> Global Registry
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content: Accessible Patients */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-sora text-xl font-semibold flex items-center gap-2">
                <FileText className="h-5 w-5 text-[#0B8A96]" />
                Accessible Patients
              </h2>
              <Badge variant="secondary" className="bg-[#0B8A96]/10 text-[#0B8A96] border-none">
                {patients.length} Active Access
              </Badge>
            </div>

            {loading ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <div className="h-8 w-8 border-4 border-t-[#0B8A96] border-slate-200 rounded-full animate-spin" />
                <p className="text-slate-500 text-sm">Loading records...</p>
              </div>
            ) : patients.length === 0 ? (
              <EmptyState
                icon={<ShieldAlert className="h-12 w-12 text-slate-300" />}
                title="No patients found"
                description="You don't currently have active cross-facility access to any patients. Search the global registry to request access."
              />
            ) : (
              <div className="space-y-4">
                {patients.map((p) => (
                  <div 
                    key={p.global_patient_id}
                    onClick={() => router.push(`/cross-facility-records/${p.global_patient_id}`)}
                    className="group relative flex items-center justify-between p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-[#0B8A96] hover:shadow-md transition-all cursor-pointer"
                  >
                    <div className="flex items-center gap-4">
                      <div className="h-12 w-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-400 font-bold text-lg">
                        {p.first_name[0]}{p.last_name[0]}
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-900 dark:text-white group-hover:text-[#0B8A96] transition-colors">
                          {p.full_name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-slate-500 dark:text-slate-500 font-mono">
                            {p.global_patient_id.slice(0, 8)}
                          </span>
                          <div className="flex gap-1">
                            {p.access_reasons?.map(reason => (
                              <Badge key={reason} variant="outline" className="text-[10px] py-0 px-1.5 uppercase font-medium border-slate-200 text-slate-500">
                                {reason.replace('_', ' ')}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-slate-300 group-hover:text-[#0B8A96] group-hover:translate-x-1 transition-all" />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar: Search & Tools */}
        <div className="space-y-6">
          <Card className="p-6 bg-[#0B8A96] text-white border-none shadow-lg">
            <h2 className="font-sora text-lg font-semibold mb-4 flex items-center gap-2">
              <Search className="h-5 w-5" />
              Search Network
            </h2>
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="relative">
                <Input 
                  placeholder="ID, Name, or Phone..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-white/10 border-white/20 text-white placeholder:text-white/60 focus:bg-white/20 pr-10"
                />
                <Button 
                  type="submit" 
                  size="icon" 
                  variant="ghost" 
                  className="absolute right-0 top-0 h-full text-white/80 hover:bg-transparent hover:text-white"
                  disabled={searchLoading}
                >
                  {searchLoading ? <div className="h-4 w-4 border-2 border-white/50 border-t-white rounded-full animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-white/70 italic">
                Querying the Central Patient Registry (Ghana Health ID, National ID)
              </p>
            </form>

            {searchResults.length > 0 && (
              <div className="mt-6 pt-6 border-t border-white/20 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-white/60">Results</p>
                {searchResults.map(p => (
                  <div 
                    key={p.global_patient_id}
                    onClick={() => router.push(`/cross-facility-records/${p.global_patient_id}`)}
                    className="flex items-center justify-between p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors cursor-pointer group"
                  >
                    <div className="text-sm">
                      <p className="font-medium">{p.full_name}</p>
                      <p className="text-[10px] text-white/60 font-mono">{p.ghana_health_id || 'No ID'}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-white/40 group-hover:text-white" />
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-6">
            <h2 className="font-sora text-lg font-semibold mb-4 flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Emergency Access
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
              If a patient is unconscious or in a life-threatening emergency, search for the patient above.
              On the patient detail page you will be presented with a Break-Glass option if you do not have consent.
            </p>
          </Card>

          <Card className="p-6">
            <h2 className="font-sora text-lg font-semibold mb-4 flex items-center gap-2">
              <History className="h-5 w-5 text-slate-400" />
              Recent Referrals
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              Accepted referrals grant temporary summary access to records.
            </p>
            <Button variant="ghost" className="w-full text-[#0B8A96] hover:bg-[#0B8A96]/5" onClick={() => router.push("/referrals")}>
              View Referrals <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
