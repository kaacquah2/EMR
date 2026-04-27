"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { useToast } from "@/lib/toast-context";
import { Clock, AlertCircle, CheckCircle2 } from "lucide-react";

interface ReceptionistAppointmentRow {
  id: string;
  patient_id: string;
  patient_name: string;
  scheduled_at: string;
  status: "scheduled" | "checked_in" | "completed" | "cancelled" | "no_show";
  appointment_with_department?: string | null;
  appointment_with_doctor?: string | null;
  provider_name?: string;
}

interface ReceptionistDashboardPayload {
  appointments_today: number;
  checked_in_count: number;
  no_show_count: number;
  remaining_count: number;
  appointments: ReceptionistAppointmentRow[];
}

export function ReceptionistAppointmentUI() {
  const api = useApi();
  const toast = useToast();
  const [metrics, setMetrics] = useState<ReceptionistDashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingIn, setCheckingIn] = useState<Record<string, boolean>>({});

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get<ReceptionistDashboardPayload>("/dashboard");
      setMetrics(response);
    } catch (error) {
      if (!isBenignApiNetworkFailure(error)) console.error("Failed to fetch metrics:", error);
      toast.error(
        isBenignApiNetworkFailure(error)
          ? "Could not reach the API. Check that the backend is running."
          : "Failed to load appointments. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }, [api, toast]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);
  usePollWhenVisible(fetchMetrics, 60_000, true);

  const handleCheckIn = async (appointmentId: string) => {
    try {
      setCheckingIn((prev) => ({ ...prev, [appointmentId]: true }));
      await api.post(`/appointments/${appointmentId}/check-in`, {});
      await fetchMetrics();
      toast.success("Patient checked in.");
    } catch (error) {
      if (!isBenignApiNetworkFailure(error)) console.error("Failed to check in patient:", error);
      toast.error(
        isBenignApiNetworkFailure(error) ? "Could not reach the API." : "Failed to check in patient."
      );
    } finally {
      setCheckingIn((prev) => ({ ...prev, [appointmentId]: false }));
    }
  };

  if (loading || !metrics) {
    return <div className="text-center py-8">Loading appointments...</div>;
  }

  const statusPill = (status: ReceptionistAppointmentRow["status"]) => {
    if (status === "checked_in") return "bg-green-100 text-green-800";
    if (status === "no_show") return "bg-red-100 text-red-800";
    if (status === "cancelled") return "bg-slate-200 text-slate-600 line-through";
    if (status === "completed") return "bg-blue-100 text-blue-800";
    return "bg-amber-100 text-amber-800";
  };

  const formatTime24 = (iso: string) =>
    new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });

  // Get arrival status breakdown
  const waitingCount = metrics.appointments.filter((a) => a.status === "scheduled").length;
  const beingSeenCount = metrics.appointments.filter((a) => a.status === "checked_in").length;

  // Get next 5 appointments for timeline
  const nextAppointments = metrics.appointments
    .filter((a) => a.status === "scheduled")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 5);

  const timeUntilAppointment = (scheduledAt: string): string => {
    const now = new Date();
    const apptTime = new Date(scheduledAt);
    const diffMinutes = Math.round((apptTime.getTime() - now.getTime()) / (1000 * 60));

    if (diffMinutes < 0) return "Overdue";
    if (diffMinutes === 0) return "Now";
    if (diffMinutes < 60) return `In ${diffMinutes}m`;
    const hours = Math.floor(diffMinutes / 60);
    const mins = diffMinutes % 60;
    return `In ${hours}h ${mins}m`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Reception Desk Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">
            Today&apos;s appointments and quick check-in
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card accent="teal">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Today&apos;s appointments</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.appointments_today}
            </p>
          </CardContent>
        </Card>

        <Card accent="green">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Checked in</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.checked_in_count}
            </p>
          </CardContent>
        </Card>

        <Card accent="red">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">No-shows</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.no_show_count}
            </p>
          </CardContent>
        </Card>

        <Card accent="blue">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Remaining today</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {metrics.remaining_count}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Queue Status Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Queue Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 border border-slate-200 rounded-lg bg-amber-50">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="h-5 w-5 text-amber-600" />
                <p className="font-medium text-amber-900">Waiting</p>
              </div>
              <p className="text-3xl font-bold text-amber-900">{waitingCount}</p>
              <p className="text-xs text-amber-700 mt-1">Patients awaiting check-in</p>
            </div>

            <div className="p-4 border border-slate-200 rounded-lg bg-green-50">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <p className="font-medium text-green-900">Being Seen</p>
              </div>
              <p className="text-3xl font-bold text-green-900">{beingSeenCount}</p>
              <p className="text-xs text-green-700 mt-1">Patients with provider</p>
            </div>

            <div className="p-4 border border-slate-200 rounded-lg bg-blue-50">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-5 w-5 text-blue-600" />
                <p className="font-medium text-blue-900">No-Shows</p>
              </div>
              <p className="text-3xl font-bold text-blue-900">{metrics.no_show_count}</p>
              <p className="text-xs text-blue-700 mt-1">Did not arrive</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Arrival Timeline Section */}
      {nextAppointments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Next Appointments</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {nextAppointments.map((apt, idx) => {
                const timeLeft = timeUntilAppointment(apt.scheduled_at);
                const isOverdue = timeLeft === "Overdue";
                const isImminient = !isOverdue && (timeLeft === "Now" || timeLeft.startsWith("In") && parseInt(timeLeft.match(/\d+/)?.[0] || "0") < 15);

                return (
                  <div
                    key={apt.id}
                    className={`p-3 border rounded-lg flex items-center justify-between ${
                      isOverdue
                        ? "border-red-300 bg-red-50"
                        : isImminient
                          ? "border-amber-300 bg-amber-50"
                          : "border-slate-200 bg-slate-50"
                    }`}
                  >
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`mt-1 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        isOverdue
                          ? "bg-red-200 text-red-800"
                          : isImminient
                            ? "bg-amber-200 text-amber-800"
                            : "bg-slate-200 text-slate-800"
                      }`}>
                        {idx + 1}
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{apt.patient_name}</p>
                        <p className="text-sm text-slate-600">{apt.appointment_with_department ?? "Appointment"}</p>
                        {apt.appointment_with_doctor && (
                          <p className="text-xs text-slate-500">{apt.appointment_with_doctor}</p>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`font-semibold text-sm ${
                        isOverdue ? "text-red-700" : isImminient ? "text-amber-700" : "text-slate-700"
                      }`}>
                        {formatTime24(apt.scheduled_at)}
                      </p>
                      <p className={`text-xs font-medium ${
                        isOverdue ? "text-red-600" : isImminient ? "text-amber-600" : "text-slate-500"
                      }`}>
                        {timeLeft}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Appointments</CardTitle>
        </CardHeader>
        <CardContent>
          {metrics.appointments.length > 0 ? (
            <div className="space-y-3">
              {metrics.appointments.map((apt) => (
                <div
                  key={apt.id}
                  className="flex items-center justify-between p-3 border border-slate-200 rounded-lg hover:bg-slate-50"
                >
                  <div>
                    <div className="font-medium text-slate-900">{apt.patient_name}</div>
                    <div className="text-sm text-slate-600">
                      [{formatTime24(apt.scheduled_at)}] {apt.appointment_with_department ?? "Appointment"}
                    </div>
                    <div className="text-sm text-slate-600">
                      {apt.appointment_with_doctor ?? "Doctor not assigned"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-semibold ${statusPill(apt.status)}`}
                    >
                      {apt.status === "checked_in"
                        ? "CHECKED IN"
                        : apt.status === "no_show"
                          ? "NO-SHOW"
                          : apt.status.toUpperCase()}
                    </span>
                    {apt.status === "scheduled" && (
                      <Button
                        size="sm"
                        data-testid={`checkin-button-${apt.id}`}
                        onClick={() => handleCheckIn(apt.id)}
                        disabled={!!checkingIn[apt.id]}
                      >
                        {checkingIn[apt.id] ? "Checking In..." : "Check In ->"}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-8 text-slate-500">
              No appointments scheduled for today
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
