"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Bed, 
  UserPlus, 
  ArrowLeftRight, 
  Wrench, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  ArrowRight,
  UserCheck
} from "lucide-react";

interface BedInfo {
  id: string;
  bed_code: string;
  status: string; // available, occupied, reserved, maintenance
  ward_id: string;
  ward_name: string;
}

interface AdmissionDetail {
  admission_id: string;
  patient_id: string;
  patient_name: string;
  ghana_health_id: string;
  ward_id: string;
  ward_name: string;
  bed_id?: string | null;
  bed_code?: string | null;
  admitted_at: string;
  admitted_by: string;
}

interface BedDashboardData {
  bed_code: string;
  patient_id: string | null;
  patient_name: string | null;
  age: number | null;
  gender: string | null;
  admission_date: string | null;
  status: "stable" | "watch" | "critical" | "vacant";
  last_vitals_at: string | null;
  vitals_overdue: boolean;
  vitals_overdue_hours: number | null;
  active_alerts_count: number;
  pending_dispense_count: number;
}

export function WardClerkDashboard() {
  const { user } = useAuth();
  const api = useApi();
  const toast = useToast();

  const [dashboardBeds, setDashboardBeds] = useState<BedDashboardData[]>([]);
  const [dbBedsMapping, setDbBedsMapping] = useState<BedInfo[]>([]);
  const [allWardAdmissions, setAllWardAdmissions] = useState<AdmissionDetail[]>([]);
  const [unassignedAdmissions, setUnassignedAdmissions] = useState<AdmissionDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Dialog state for Transfer Patient
  const [transferTarget, setTransferTarget] = useState<{
    admissionId: string;
    patientName: string;
    currentBedCode: string;
  } | null>(null);
  const [transferLoading, setTransferLoading] = useState(false);

  // Dialog state for Assign Bed
  const [assignTarget, setAssignTarget] = useState<{
    admissionId: string;
    patientName: string;
  } | null>(null);
  const [assignLoading, setAssignLoading] = useState(false);

  const wardId = user?.ward_id;
  const wardName = user?.ward_name || "Assigned Ward";

  const loadData = useCallback(async (isSilent = false) => {
    if (!wardId) {
      setLoading(false);
      return;
    }
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      // Fetch Ward Bed Dashboard status
      const dashResp = await api.get<{ data: BedDashboardData[] }>(
        `/admissions/ward/${wardId}/dashboard`
      );
      setDashboardBeds(dashResp.data || []);

      // Fetch Wards Bed Info Mapping (for Bed IDs & maintenance toggles)
      const bedsResp = await api.get<{ data: BedInfo[] }>(
        `/admin/wards/${wardId}/beds`
      );
      setDbBedsMapping(bedsResp.data || []);

      // Fetch Active Admissions for this ward
      const admissionsResp = await api.get<{ data: AdmissionDetail[] }>("/admissions");
      const wardAdmissions = (admissionsResp.data || []).filter(
        (adm) => adm.ward_id === wardId
      );
      setAllWardAdmissions(wardAdmissions);
      setUnassignedAdmissions(wardAdmissions.filter((adm) => !adm.bed_id));

    } catch (err) {
      console.error("Failed to load Ward Clerk Dashboard data:", err);
      toast.error("Failed to fetch dashboard data. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, wardId, toast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);
  usePollWhenVisible(() => loadData(true), 60_000, true);

  // Correlate bed dashboard status with DB Bed Info to get the DB ID and status
  const integratedBeds = useMemo(() => {
    return dashboardBeds.map((dashBed) => {
      const mapping = dbBedsMapping.find((m) => m.bed_code === dashBed.bed_code);
      return {
        ...dashBed,
        id: mapping?.id || "",
        dbStatus: mapping?.status || (dashBed.patient_id ? "occupied" : "available"),
      };
    });
  }, [dashboardBeds, dbBedsMapping]);

  // Statistics calculations
  const stats = useMemo(() => {
    const total = integratedBeds.length;
    const occupied = integratedBeds.filter((b) => b.patient_id !== null).length;
    const maintenance = dbBedsMapping.filter((b) => b.status === "maintenance").length;
    const available = total - occupied - maintenance;
    return { total, occupied, available, maintenance };
  }, [integratedBeds, dbBedsMapping]);

  // Find the active admission ID for a patient using already-fetched ward admissions.
  // Does NOT filter on bed_code — patients in occupied beds must also be transferable.
  const findAdmissionId = (patientId: string): string | null => {
    const found = allWardAdmissions.find((a) => a.patient_id === patientId);
    return found?.admission_id || null;
  };

  const handleUpdateBedStatus = async (bedId: string, newStatus: string) => {
    if (!bedId) return;
    try {
      await api.patch(`/admin/beds/${bedId}`, { status: newStatus });
      toast.success(`Bed status updated to ${newStatus}`);
      void loadData(true);
    } catch (err) {
      console.error("Failed to update bed status:", err);
      toast.error("Failed to update bed status");
    }
  };

  const handleTransferSubmit = async (targetBedId: string) => {
    if (!transferTarget || !targetBedId) return;
    setTransferLoading(true);
    try {
      await api.post(`/admissions/${transferTarget.admissionId}/transfer`, {
        to_ward_id: wardId,
        to_bed_id: targetBedId,
        reason: "Transferred by Ward Clerk",
      });
      toast.success(`${transferTarget.patientName} transferred successfully.`);
      setTransferTarget(null);
      void loadData(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to transfer patient.");
    } finally {
      setTransferLoading(false);
    }
  };

  const handleAssignSubmit = async (admissionId: string, targetBedId: string) => {
    if (!targetBedId || !admissionId) return;
    setAssignLoading(true);
    try {
      await api.post(`/admissions/${admissionId}/transfer`, {
        to_ward_id: wardId,
        to_bed_id: targetBedId,
        reason: "Bed assigned by Ward Clerk",
      });
      toast.success("Bed assigned successfully.");
      setAssignTarget(null);
      void loadData(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign bed.");
    } finally {
      setAssignLoading(false);
    }
  };

  // Available beds (vacant & status == available) for transfer/assignment options
  const availableBedsForSelect = useMemo(() => {
    return integratedBeds.filter((b) => b.dbStatus === "available" && !b.patient_id);
  }, [integratedBeds]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 dark:text-slate-500">
        <div className="flex flex-col items-center gap-2">
          <RefreshCw className="h-8 w-8 animate-spin text-[#0EAFBE]" />
          <span>Loading Ward Dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Dashboard Heading */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold font-sora text-slate-900 dark:text-slate-100">
            Ward Administration & Bed Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Ward {wardName} · Clerk Console
          </p>
        </div>
        <Button 
          onClick={() => void loadData(true)} 
          variant="secondary" 
          size="sm"
          className="flex items-center gap-1.5"
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? "Refreshing..." : "Refresh Data"}
        </Button>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-l-4 border-l-[#0EAFBE] shadow-sm bg-white dark:bg-slate-900">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Total Ward Beds</p>
            <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">{stats.total}</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-[#e24b4a] shadow-sm bg-white dark:bg-slate-900">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Occupied Beds</p>
            <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">{stats.occupied}</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-[#639922] shadow-sm bg-white dark:bg-slate-900">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Available Beds</p>
            <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">{stats.available}</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-[#ef9f27] shadow-sm bg-white dark:bg-slate-900">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Under Maintenance</p>
            <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">{stats.maintenance}</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Bed Management + Admissions Worklist */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Bed Grid Column */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="shadow-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-4">
              <CardTitle className="text-lg font-bold flex items-center gap-2 text-slate-800 dark:text-slate-100">
                <Bed className="h-5 w-5 text-[#0EAFBE]" />
                Live Ward Bed Grid
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {integratedBeds.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                  <Bed className="h-12 w-12 stroke-[1] mb-2" />
                  <p>No beds configured for this ward.</p>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                  {integratedBeds.map((bed) => {
                    const isOccupied = !!bed.patient_id;
                    const isMaintenance = bed.dbStatus === "maintenance";
                    
                    return (
                      <div
                        key={bed.bed_code}
                        className={`rounded-xl border p-4 transition-all flex flex-col justify-between h-full bg-white dark:bg-slate-950 ${
                          isOccupied
                            ? bed.status === "critical"
                              ? "border-l-4 border-l-[#E24B4A] border-slate-200 dark:border-slate-800 shadow-sm"
                              : bed.status === "watch"
                                ? "border-l-4 border-l-[#EF9F27] border-slate-200 dark:border-slate-800 shadow-sm"
                                : "border-l-4 border-l-[#639922] border-slate-200 dark:border-slate-800 shadow-sm"
                            : isMaintenance
                              ? "border-l-4 border-l-[#ef9f27] border-slate-200 dark:border-slate-800 bg-amber-50/10"
                              : "border-slate-200 dark:border-slate-800 border-dashed"
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-bold text-slate-900 dark:text-slate-100">
                              {bed.bed_code}
                            </span>
                            <Badge 
                              variant={isOccupied ? "default" : isMaintenance ? "pending" : "secondary"}
                              className="text-[10px] uppercase font-semibold"
                            >
                              {isOccupied ? "Occupied" : isMaintenance ? "Maintenance" : "Available"}
                            </Badge>
                          </div>

                          {isOccupied ? (
                            <div className="mt-3 space-y-1">
                              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 line-clamp-1">
                                {bed.patient_name}
                              </p>
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                {bed.age}y · {bed.gender}
                              </p>
                              <div className="mt-2 text-[11px] space-y-0.5 text-slate-500 dark:text-slate-400">
                                {bed.active_alerts_count > 0 && (
                                  <span className="inline-flex items-center gap-1 text-[#E24B4A] font-semibold">
                                    <AlertTriangle className="h-3 w-3" />
                                    {bed.active_alerts_count} Active Alerts
                                  </span>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="mt-4 flex flex-col items-center justify-center py-4 text-slate-300 dark:text-slate-700">
                              <Bed className="h-8 w-8 stroke-[1]" />
                              <span className="text-[10px] uppercase tracking-wider font-semibold mt-1">Vacant</span>
                            </div>
                          )}
                        </div>

                        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex gap-2">
                          {isOccupied ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              className="w-full text-xs flex items-center justify-center gap-1"
                              onClick={() => {
                                const admissionId = findAdmissionId(bed.patient_id!);
                                if (admissionId) {
                                  setTransferTarget({
                                    admissionId,
                                    patientName: bed.patient_name || "Patient",
                                    currentBedCode: bed.bed_code,
                                  });
                                } else {
                                  toast.error("Could not locate active admission ID for patient.");
                                }
                              }}
                            >
                              <ArrowLeftRight className="h-3.5 w-3.5" />
                              Transfer
                            </Button>
                          ) : (
                            <>
                              {isMaintenance ? (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  className="w-full text-xs flex items-center justify-center gap-1"
                                  onClick={() => void handleUpdateBedStatus(bed.id, "available")}
                                >
                                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                  Mark Ready
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="w-full text-xs text-amber-600 hover:text-amber-700 flex items-center justify-center gap-1"
                                  onClick={() => void handleUpdateBedStatus(bed.id, "maintenance")}
                                >
                                  <Wrench className="h-3.5 w-3.5" />
                                  Maintenance
                                </Button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Admissions Worklist Column */}
        <div className="space-y-4">
          <Card className="shadow-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-4">
              <CardTitle className="text-lg font-bold flex items-center gap-2 text-slate-800 dark:text-slate-100">
                <UserPlus className="h-5 w-5 text-[#0EAFBE]" />
                Unassigned Admissions ({unassignedAdmissions.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              {unassignedAdmissions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                  <UserCheck className="h-12 w-12 stroke-[1] mb-2 text-slate-300" />
                  <p className="text-sm text-center">All admitted patients have been assigned to beds.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {unassignedAdmissions.map((adm) => (
                    <div
                      key={adm.admission_id}
                      className="rounded-lg border border-slate-150 dark:border-slate-800 p-3 bg-slate-50/50 dark:bg-slate-950/20 flex flex-col justify-between gap-3"
                    >
                      <div>
                        <h4 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                          {adm.patient_name}
                        </h4>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          ID: {adm.ghana_health_id}
                        </p>
                        <p className="text-[11px] text-slate-400 mt-2">
                          Admitted {new Date(adm.admitted_at).toLocaleDateString()} by {adm.admitted_by}
                        </p>
                      </div>

                      <Button
                        size="sm"
                        className="w-full text-xs bg-[#0EAFBE] hover:bg-[#0B8A96] text-white flex items-center justify-center gap-1.5"
                        onClick={() => {
                          setAssignTarget({
                            admissionId: adm.admission_id,
                            patientName: adm.patient_name,
                          });
                        }}
                      >
                        <Bed className="h-3.5 w-3.5" />
                        Allocate Bed
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Transfer Patient Modal */}
      {transferTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl p-6 shadow-2xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">
              Transfer Bed Assignment
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              Select an available bed to transfer <strong>{transferTarget.patientName}</strong> from bed <strong>{transferTarget.currentBedCode}</strong>.
            </p>

            {availableBedsForSelect.length === 0 ? (
              <div className="rounded-lg bg-amber-50 dark:bg-amber-950/20 p-3 text-amber-700 dark:text-amber-400 text-xs flex gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <span>No vacant available beds in this ward. Release a bed or mark a maintenance bed as ready first.</span>
              </div>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto mb-6 pr-1">
                {availableBedsForSelect.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => void handleTransferSubmit(b.id)}
                    disabled={transferLoading}
                    className="w-full text-left flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-[#0EAFBE]/10 hover:border-[#0EAFBE] transition-all group"
                  >
                    <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">{b.bed_code}</span>
                    <span className="text-xs text-[#0EAFBE] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      Transfer here <ArrowRight className="h-3 w-3" />
                    </span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTransferTarget(null)}
                disabled={transferLoading}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Bed Modal */}
      {assignTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl p-6 shadow-2xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">
              Allocate Bed Assignment
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              Select an available bed to assign to <strong>{assignTarget.patientName}</strong>.
            </p>

            {availableBedsForSelect.length === 0 ? (
              <div className="rounded-lg bg-amber-50 dark:bg-amber-950/20 p-3 text-amber-700 dark:text-amber-400 text-xs flex gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <span>No vacant available beds in this ward. Release a bed or mark a maintenance bed as ready first.</span>
              </div>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto mb-6 pr-1">
                {availableBedsForSelect.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => void handleAssignSubmit(assignTarget.admissionId, b.id)}
                    disabled={assignLoading}
                    className="w-full text-left flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-[#0EAFBE]/10 hover:border-[#0EAFBE] transition-all group"
                  >
                    <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">{b.bed_code}</span>
                    <span className="text-xs text-[#0EAFBE] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      Assign bed <ArrowRight className="h-3 w-3" />
                    </span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setAssignTarget(null)}
                disabled={assignLoading}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
