"use client";

import React, { useMemo, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useAppointments, useCreateAppointment } from "@/hooks/use-appointments";
import { usePatientSearch } from "@/hooks/use-patients";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/DatePicker";
import SearchableSelect from "@/components/ui/SearchableSelect";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import AppointmentBulkImportForm from "@/components/features/AppointmentBulkImportForm";
import AppointmentBulkActions from "@/components/features/AppointmentBulkActions";
import AppointmentReminderUI from "@/components/features/AppointmentReminderUI";

const APPOINTMENT_ROLES = ["super_admin", "hospital_admin", "doctor", "nurse", "receptionist"];
const DEPARTMENTS = [
  "General Medicine",
  "Cardiology",
  "Obs-Gyn",
  "Paediatrics",
  "Orthopaedics",
];
type ViewMode = "list" | "day" | "week";
type BookingMode = "single" | "bulk";
type PageTab = "appointments" | "bulk-actions" | "reminders";

export default function AppointmentsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const toast = useToast();
  const isReceptionist = user?.role === "receptionist";
  const [pageTab, setPageTab] = useState<PageTab>("appointments");
  const [dateFilter, setDateFilter] = useState(() => {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  });
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [bookingMode, setBookingMode] = useState<BookingMode>("single");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [departmentFilter, setDepartmentFilter] = useState<string>("");
  const [createOpen, setCreateOpen] = useState(isReceptionist);
  const [createPatientId, setCreatePatientId] = useState("");
  const [createScheduledAt, setCreateScheduledAt] = useState(""); // datetime-local
  const [createDepartment, setCreateDepartment] = useState("");
  const [createDoctorId, setCreateDoctorId] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [availabilityMessage, setAvailabilityMessage] = useState<string>("");
  const [availabilitySlots, setAvailabilitySlots] = useState<string[]>([]);
  const [cancelReason, setCancelReason] = useState<Record<string, string>>({});
  const [rescheduleAt, setRescheduleAt] = useState<Record<string, string>>({});
  const [inlineLoading, setInlineLoading] = useState<Record<string, boolean>>({});
  const [checkingAvailability, setCheckingAvailability] = useState(false);

  const { appointments, loading, fetch } = useAppointments(
    dateFilter || undefined,
    undefined,
    statusFilter || undefined,
    departmentFilter || undefined
  );
  const { create, loading: creating } = useCreateAppointment();
  const { results: searchResults, search } = usePatientSearch();

  const canManage =
    user?.role === "doctor" ||
    user?.role === "hospital_admin" ||
    user?.role === "super_admin" ||
    user?.role === "receptionist";
  const canAccess = user?.role && APPOINTMENT_ROLES.includes(user.role);
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  const formatTime24 = (iso: string) =>
    new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });

  const checkInWindow = (iso: string) => {
    const scheduled = new Date(iso).getTime();
    const now = Date.now();
    const from = scheduled - 2 * 60 * 60 * 1000;
    const to = scheduled + 2 * 60 * 60 * 1000;
    return { enabled: now >= from && now <= to, from };
  };

  const canMarkNoShow = (iso: string) => Date.now() >= new Date(iso).getTime() + 30 * 60 * 1000;

  useEffect(() => {
    const run = async () => {
      if (!createScheduledAt || !createDepartment) {
        setAvailabilityMessage("");
        setAvailabilitySlots([]);
        return;
      }
      setCheckingAvailability(true);
      try {
        const datetime = new Date(createScheduledAt).toISOString();
        const params = new URLSearchParams({
          datetime,
          department_id: createDepartment,
        });
        if (createDoctorId.trim()) params.set("doctor_id", createDoctorId.trim());
        const res = await api.get<{ conflict: boolean; message?: string; available_slots?: string[] }>(
          `/appointments/check-availability?${params}`
        );
        if (res.conflict) {
          setAvailabilityMessage(res.message ?? "Selected time has a conflict.");
          setAvailabilitySlots(res.available_slots ?? []);
        } else {
          setAvailabilityMessage("");
          setAvailabilitySlots([]);
        }
      } catch {
        setAvailabilityMessage("");
        setAvailabilitySlots([]);
      } finally {
        setCheckingAvailability(false);
      }
    };
    const t = setTimeout(() => {
      void run();
    }, 150);
    return () => clearTimeout(t);
  }, [api, createScheduledAt, createDepartment, createDoctorId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createPatientId || !createScheduledAt || !createDepartment) return;
    try {
      await create({
        patient_id: createPatientId,
        appointment_date: new Date(createScheduledAt).toISOString(),
        department_id: createDepartment,
        doctor_id: createDoctorId.trim() || undefined,
        notes: createNotes.trim() || undefined,
      });
      setCreatePatientId("");
      setCreateScheduledAt("");
      setCreateDepartment("");
      setCreateDoctorId("");
      setCreateNotes("");
      setAvailabilityMessage("");
      setAvailabilitySlots([]);
      toast.success("Appointment booked.");
      fetch();
    } catch {
      toast.error("Could not book appointment.");
    }
  };

  const mutateAppointment = async (
    id: string,
    fn: () => Promise<void>,
    okMessage: string,
    errorMessage: string
  ) => {
    setInlineLoading((prev) => ({ ...prev, [id]: true }));
    try {
      await fn();
      toast.success(okMessage);
      await fetch();
    } catch {
      toast.error(errorMessage);
    } finally {
      setInlineLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const groupedByHour = useMemo(() => {
    const map: Record<string, typeof appointments> = {};
    for (const apt of appointments) {
      const key = formatTime24(apt.scheduled_at);
      if (!map[key]) map[key] = [];
      map[key].push(apt);
    }
    return map;
  }, [appointments]);

  const statusClass = (status: string) => {
    if (status === "scheduled") return "bg-slate-100 text-slate-700";
    if (status === "checked_in") return "bg-green-100 text-green-800";
    if (status === "completed") return "bg-blue-100 text-blue-800";
    if (status === "no_show") return "bg-red-100 text-red-800";
    if (status === "cancelled") return "bg-slate-200 text-slate-600 line-through";
    return "bg-slate-100 text-slate-700";
  };

  if (user && !canAccess) {
    return <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">Redirecting...</div>;
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Appointments" }]} />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Appointments</h1>
        {canManage && pageTab === "appointments" && (
          <Button onClick={() => setCreateOpen((s) => !s)}>
            {createOpen ? "Hide booking form" : "Book appointment"}
          </Button>
        )}
      </div>

      {/* Page Level Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <div className="flex gap-8">
          {(["appointments", "bulk-actions", "reminders"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setPageTab(tab)}
              className={`px-4 py-3 font-medium text-sm border-b-2 ${
                pageTab === tab
                  ? "border-[#0EAFBE] text-[#0EAFBE]"
                  : "border-transparent text-slate-500 dark:text-slate-500 hover:text-slate-900 dark:text-slate-100"
              }`}
            >
              {tab === "appointments" && "Appointments"}
              {tab === "bulk-actions" && "Bulk Actions"}
              {tab === "reminders" && "Reminders"}
            </button>
          ))}
        </div>
      </div>

      {/* Appointments Tab */}
      {pageTab === "appointments" && (
        <>
      <div className="flex flex-wrap gap-2">
        <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 bg-white p-1">
          {(["list", "day", "week"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              className={`rounded px-3 py-1 text-sm ${
                viewMode === mode ? "bg-[#0EAFBE] text-white" : "text-[#334155]"
              }`}
            >
              {mode === "list" ? "List" : mode === "day" ? "Day grid" : "Week grid"}
            </button>
          ))}
        </div>
        <div className="w-40">
          <DatePicker
            value={dateFilter ? new Date(dateFilter + "T12:00:00") : null}
            onChange={(date) => {
              if (date) {
                const y = date.getFullYear();
                const m = String(date.getMonth() + 1).padStart(2, '0');
                const d = String(date.getDate()).padStart(2, '0');
                setDateFilter(`${y}-${m}-${d}`);
              } else {
                setDateFilter("");
              }
            }}
            format="YYYY-MM-DD"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="checked_in">Checked In</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="no_show">No Show</option>
        </select>
        <div className="w-48 z-10">
          <SearchableSelect
            options={["", ...DEPARTMENTS]}
            value={departmentFilter}
            onChange={(val) => setDepartmentFilter(val as string)}
            getLabel={(val) => val ? val : "All departments"}
            getValue={(val) => val}
            placeholder="All departments"
          />
        </div>
      </div>

      {createOpen && (
        <Card className="p-6">
          <div className="mb-4 flex gap-2 border-b border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={() => setBookingMode("single")}
              className={`px-4 py-2 text-sm font-medium ${
                bookingMode === "single"
                  ? "border-b-2 border-[#0EAFBE] text-[#0EAFBE]"
                  : "text-slate-500 dark:text-slate-500"
              }`}
            >
              Single Booking
            </button>
            <button
              type="button"
              onClick={() => setBookingMode("bulk")}
              className={`px-4 py-2 text-sm font-medium ${
                bookingMode === "bulk"
                  ? "border-b-2 border-[#0EAFBE] text-[#0EAFBE]"
                  : "text-slate-500 dark:text-slate-500"
              }`}
            >
              Bulk Import
            </button>
          </div>
          {bookingMode === "single" && (
            <>
              <h2 className="font-sora text-lg font-bold text-slate-900 dark:text-slate-100">Book new appointment</h2>
              <form onSubmit={handleCreate} className="mt-4 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Search patient</label>
                  <Input
                    placeholder="Search by name or Ghana Health ID"
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v.trim().length >= 2) search(v, "name");
                    }}
                  />
                  {searchResults.length > 0 && (
                <ul className="mt-1 max-h-32 overflow-y-auto rounded border border-slate-200 dark:border-slate-800 bg-white">
                  {searchResults.slice(0, 6).map((p) => (
                    <li
                      key={p.patient_id}
                      className="cursor-pointer px-3 py-2 text-sm hover:bg-slate-100 dark:bg-slate-900"
                      onClick={() => setCreatePatientId(p.patient_id)}
                    >
                      {p.full_name} ({p.ghana_health_id})
                    </li>
                  ))}
                </ul>
              )}
              {createPatientId && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">Selected patient ID: {createPatientId}</p>
              )}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Department *</label>
                <div className="z-10 relative">
                  <SearchableSelect
                    options={DEPARTMENTS}
                    value={createDepartment}
                    onChange={(val) => setCreateDepartment(val as string)}
                    getLabel={(val) => val}
                    getValue={(val) => val}
                    placeholder="Select department"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Doctor ID (optional)</label>
                <Input
                  value={createDoctorId}
                  onChange={(e) => setCreateDoctorId(e.target.value)}
                  placeholder="Leave empty to assign later"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Date and time *</label>
              <div className="z-10 relative">
                <DatePicker
                  value={createScheduledAt ? new Date(createScheduledAt) : null}
                  onChange={(date) => {
                    if (date) {
                      const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
                        .toISOString()
                        .slice(0, 16);
                      setCreateScheduledAt(local);
                    } else {
                      setCreateScheduledAt("");
                    }
                  }}
                  showTime
                  format="YYYY-MM-DD"
                />
              </div>
            </div>
            {checkingAvailability && <p className="text-xs text-slate-500 dark:text-slate-500">Checking availability...</p>}
            {!!availabilityMessage && (
              <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <p>{availabilityMessage}</p>
                {availabilitySlots.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {availabilitySlots.map((slot) => (
                      <button
                        key={slot}
                        type="button"
                        className="rounded-full border border-amber-300 px-3 py-1 text-xs"
                        onClick={() => {
                          if (!createScheduledAt) return;
                          const base = new Date(createScheduledAt);
                          const [hh, mm] = slot.split(":").map(Number);
                          base.setHours(hh, mm, 0, 0);
                          const local = new Date(base.getTime() - base.getTimezoneOffset() * 60000)
                            .toISOString()
                            .slice(0, 16);
                          setCreateScheduledAt(local);
                        }}
                      >
                        {slot}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Notes (optional)</label>
              <Input
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                placeholder="Optional"
              />
            </div>
            <Button
              type="submit"
              disabled={creating || !createPatientId || !createScheduledAt || !createDepartment}
            >
              Save
            </Button>
          </form>
            </>
          )}
          {bookingMode === "bulk" && (
            <>
              <h2 className="font-sora text-lg font-bold text-slate-900 dark:text-slate-100">Bulk Import Appointments</h2>
              <AppointmentBulkImportForm onSuccess={() => {
                fetch();
                setBookingMode("single");
              }} />
            </>
          )}
        </Card>
      )}

      <Card className="p-6">
        {loading ? (
          <p className="text-slate-500 dark:text-slate-500">Loading...</p>
        ) : appointments.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-500">No appointments for this date/status.</p>
        ) : viewMode !== "list" ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-500 dark:text-slate-500">
              {viewMode === "day" ? "Day grid" : "Week grid"} (color coding is consistent with list view)
            </p>
            {Object.entries(groupedByHour).map(([hour, rows]) => (
              <div key={hour} className="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
                <p className="mb-2 text-sm font-semibold text-[#334155]">{hour}</p>
                <div className="flex flex-wrap gap-2">
                  {rows.map((a) => (
                    <span key={a.id} className={`rounded-full px-2 py-1 text-xs ${statusClass(a.status)}`}>
                      {a.patient_name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Time</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Patient</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Appointment</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Provider</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((a) => (
                  <tr key={a.id} className="border-b border-slate-100 dark:border-slate-900">
                    <td className="px-4 py-2 font-mono text-sm">
                      {formatTime24(a.scheduled_at)}
                    </td>
                    <td className="px-4 py-2 text-slate-900 dark:text-slate-100">
                      {a.patient_name}
                      <span className="ml-1 text-xs text-slate-500 dark:text-slate-500">{a.ghana_health_id}</span>
                    </td>
                    <td className="px-4 py-2 capitalize">Appointment with {a.appointment_type?.replace("_", " ")}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(a.status)}`}>{a.status}</span>
                    </td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-500">{a.provider_name || "—"}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-2">
                        {a.status === "scheduled" && (
                          <Button
                            size="sm"
                            onClick={() =>
                              void mutateAppointment(
                                a.id,
                                async () => {
                                  await api.post(`/appointments/${a.id}/check-in`, {});
                                },
                                "Checked in.",
                                "Check-in failed."
                              )
                            }
                            disabled={
                              inlineLoading[a.id] ||
                              !checkInWindow(a.scheduled_at).enabled
                            }
                            title={
                              checkInWindow(a.scheduled_at).enabled
                                ? ""
                                : `Check-in available from ${new Date(
                                    checkInWindow(a.scheduled_at).from
                                  ).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false })}`
                            }
                          >
                            Check In
                          </Button>
                        )}
                        {a.status === "scheduled" && canMarkNoShow(a.scheduled_at) && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              void mutateAppointment(
                                a.id,
                                async () => {
                                  await api.post(`/appointments/${a.id}/no-show`, {});
                                },
                                "Marked as no-show.",
                                "Could not mark no-show."
                              )
                            }
                            disabled={inlineLoading[a.id]}
                          >
                            Mark No-Show
                          </Button>
                        )}
                        <Input
                          type="datetime-local"
                          value={rescheduleAt[a.id] ?? ""}
                          onChange={(e) => setRescheduleAt((prev) => ({ ...prev, [a.id]: e.target.value }))}
                          className="w-44"
                        />
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!rescheduleAt[a.id] || inlineLoading[a.id]}
                          onClick={() =>
                            void mutateAppointment(
                              a.id,
                              async () => {
                                await api.patch(`/appointments/${a.id}`, {
                                  scheduled_at: new Date(rescheduleAt[a.id]).toISOString(),
                                });
                              },
                              "Rescheduled.",
                              "Could not reschedule."
                            )
                          }
                        >
                          Confirm reschedule
                        </Button>
                        <Input
                          value={cancelReason[a.id] ?? ""}
                          onChange={(e) => setCancelReason((prev) => ({ ...prev, [a.id]: e.target.value }))}
                          placeholder="Cancellation reason"
                          className="w-44"
                        />
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!(cancelReason[a.id] ?? "").trim() || inlineLoading[a.id]}
                          onClick={() =>
                            void mutateAppointment(
                              a.id,
                              async () => {
                                await api.delete(`/appointments/${a.id}/delete`, {
                                  cancellation_reason: (cancelReason[a.id] ?? "").trim(),
                                });
                              },
                              "Cancelled.",
                              "Could not cancel appointment."
                            )
                          }
                        >
                          Confirm cancellation
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {createOpen && (
        <Card className="p-6">
          <h2 className="font-sora text-lg font-bold text-slate-900 dark:text-slate-100">Schedule appointment</h2>
          <form onSubmit={handleCreate} className="mt-4 space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Patient (search then pick ID)</label>
              <Input
                placeholder="Search by name or Ghana Health ID"
                onChange={(e) => {
                  const v = e.target.value;
                  if (v.trim().length >= 2) search(v, "name");
                }}
              />
              {searchResults.length > 0 && (
                <ul className="mt-1 max-h-32 overflow-y-auto rounded border border-slate-200 dark:border-slate-800 bg-white">
                  {searchResults.slice(0, 5).map((p) => (
                    <li
                      key={p.patient_id}
                      className="cursor-pointer px-3 py-2 text-sm hover:bg-slate-100 dark:bg-slate-900"
                      onClick={() => setCreatePatientId(p.patient_id)}
                    >
                      {p.full_name} ({p.ghana_health_id})
                    </li>
                  ))}
                </ul>
              )}
              {createPatientId && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">Selected patient ID: {createPatientId}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Date & time *</label>
              <div className="z-10 relative">
                <DatePicker
                  value={createScheduledAt ? new Date(createScheduledAt) : null}
                  onChange={(date) => {
                    if (date) {
                      const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
                        .toISOString()
                        .slice(0, 16);
                      setCreateScheduledAt(local);
                    } else {
                      setCreateScheduledAt("");
                    }
                  }}
                  showTime
                  format="YYYY-MM-DD"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Notes</label>
              <Input
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={creating || !createPatientId || !createScheduledAt}>
                Save
              </Button>
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
        </>
      )}

      {/* Bulk Actions Tab */}
      {pageTab === "bulk-actions" && (
        <AppointmentBulkActions
          appointments={appointments}
          onRefresh={fetch}
        />
      )}

      {/* Reminders Tab */}
      {pageTab === "reminders" && (
        <AppointmentReminderUI />
      )}
    </div>
  );
}
