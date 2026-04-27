"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { useUsers, useWards } from "@/hooks/use-admin";
import { useFacilities } from "@/hooks/use-interop";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { SlideOver } from "@/components/features/SlideOver";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useDepartments, useLabUnits } from "@/hooks/use-admin";
import { AdminPasskeyManagement } from "@/components/features/admin/AdminPasskeyManagement";
type StaffRole = "doctor" | "nurse" | "receptionist" | "lab_technician";
const ROLE_LABEL: Record<StaffRole, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  receptionist: "Receptionist",
  lab_technician: "Lab Technician",
};
const initialInviteForm = {
  full_name: "",
  email: "",
  role: "doctor" as StaffRole,
  department_id: "",
  ward_id: "",
  lab_unit_id: "",
  gmdc_licence_number: "",
  hospital_id: "",
};

export default function AdminUsersPage() {
  const { user } = useAuth();
  const api = useApi();
  const { users, loading, fetch } = useUsers();
  const [inviteForm, setInviteForm] = useState(initialInviteForm);
  const { wards, fetch: fetchWards } = useWards(
    user?.role === "super_admin" ? (inviteForm.hospital_id || undefined) : undefined
  );
  const hospitalIdForLists = user?.role === "super_admin" ? inviteForm.hospital_id : undefined;
  const { departments, fetch: fetchDepartments } = useDepartments(hospitalIdForLists || undefined);
  const { labUnits, fetch: fetchLabUnits } = useLabUnits(hospitalIdForLists || undefined);
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupDone, setSetupDone] = useState(false);
  const facilitiesSource =
    user?.role === "super_admin" ? "superadmin_hospitals" : "interop";
  const { facilities, fetch: fetchFacilities } = useFacilities(facilitiesSource);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkHospitalId, setBulkHospitalId] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ created: number; errors: Array<{ row: number; email?: string; error: string }> } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [linkDialog, setLinkDialog] = useState<{ type: "reset" | "invite"; url: string; userEmail: string } | null>(null);
  const [actionError, setActionError] = useState("");
  const [passwordResetTarget, setPasswordResetTarget] = useState<{ user_id: string; email: string } | null>(null);
  const [passwordResetConfirmOpen, setPasswordResetConfirmOpen] = useState(false);
  const [roleChangeTarget, setRoleChangeTarget] = useState<{ user_id: string; full_name: string; fromRole: StaffRole; toRole: StaffRole } | null>(null);
  const [roleChangeConfirmOpen, setRoleChangeConfirmOpen] = useState(false);
  const inviteDeepLinkHandledRef = useRef(false);
  const haInviteDeepLinkHandledRef = useRef(false);
  const resendInviteHandledRef = useRef(false);

  const buildAppUrl = useCallback((path: string, token: string) => {
    if (typeof window === "undefined") return "";
    return `${window.location.origin}${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
  }, []);

  const handleSendPasswordReset = async (u: { user_id: string; email: string }) => {
    setActionError("");
    setActionLoading(u.user_id);
    try {
      const res = await api.post<{ token: string }>(`/admin/users/${u.user_id}/send-password-reset`, {});
      const url = buildAppUrl("/reset-password", res.token);
      setLinkDialog({ type: "reset", url, userEmail: u.email });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to generate reset link");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResetMfa = async (u: { user_id: string }) => {
    setActionError("");
    setActionLoading(u.user_id);
    try {
      await api.post(`/admin/users/${u.user_id}/reset-mfa`, {});
      fetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to reset MFA");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResendInvite = async (u: { user_id: string; email: string }) => {
    setActionError("");
    setActionLoading(u.user_id);
    try {
      const res = await api.post<{ token: string }>(`/admin/users/${u.user_id}/resend-invite`, {});
      const url = buildAppUrl("/activate", res.token);
      setLinkDialog({ type: "invite", url, userEmail: u.email });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to resend invite");
    } finally {
      setActionLoading(null);
    }
  };

  const roleImpactMessage = (fullName: string, fromRole: StaffRole, toRole: StaffRole) => {
    if (fromRole === "nurse" && toRole === "doctor") {
      return `Changing ${fullName} from Nurse to Doctor will remove their ward assignment and grant prescribing access. Confirm?`;
    }
    if (fromRole === "doctor" && toRole !== "doctor") {
      return `Changing ${fullName} from Doctor to ${ROLE_LABEL[toRole]} will revoke prescribing access and clear doctor-specific licence metadata. Confirm?`;
    }
    if (toRole === "lab_technician") {
      return `Changing ${fullName} to Lab Technician will route their workload to lab-unit queues and remove ward assignment. Confirm?`;
    }
    return `Change ${fullName} from ${ROLE_LABEL[fromRole]} to ${ROLE_LABEL[toRole]}?`;
  };

  const handleRoleChange = async () => {
    if (!roleChangeTarget) return;
    setActionError("");
    setActionLoading(roleChangeTarget.user_id);
    try {
      await api.patch(`/admin/users/${roleChangeTarget.user_id}`, {
        role: roleChangeTarget.toRole,
        reason: "Quarterly review - role reassignment",
      });
      await fetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to change role");
      throw err;
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    if (inviteOpen && user?.role === "super_admin") fetchFacilities();
    if (inviteOpen && user?.role === "hospital_admin") void fetchWards();
  }, [inviteOpen, user?.role, fetchFacilities, fetchWards]);

  useEffect(() => {
    if (typeof window === "undefined" || user?.role !== "super_admin") return;
    if (inviteDeepLinkHandledRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const hospital = params.get("hospital");
    const action = params.get("action");
    if (hospital) {
      setInviteForm((f) => ({ ...f, hospital_id: hospital }));
    }
    if (action === "invite_admin") {
      setInviteOpen(true);
      inviteDeepLinkHandledRef.current = true;
      params.delete("action");
      const qs = params.toString();
      window.history.replaceState(
        null,
        "",
        qs ? `${window.location.pathname}?${qs}` : window.location.pathname
      );
    }
  }, [user?.role]);

  useEffect(() => {
    if (typeof window === "undefined" || user?.role !== "hospital_admin") return;
    if (haInviteDeepLinkHandledRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const action = params.get("action");
    if (action !== "invite") return;
    setInviteOpen(true);
    haInviteDeepLinkHandledRef.current = true;
    params.delete("action");
    const qs = params.toString();
    window.history.replaceState(
      null,
      "",
      qs ? `${window.location.pathname}?${qs}` : window.location.pathname
    );
  }, [user?.role]);

  useEffect(() => {
    if (typeof window === "undefined" || user?.role !== "super_admin" || loading) return;
    const params = new URLSearchParams(window.location.search);
    const resendId = params.get("resendInvite");
    if (!resendId || resendInviteHandledRef.current) return;
    resendInviteHandledRef.current = true;
    const inviteeEmail =
      params.get("inviteeEmail") ||
      users.find((x) => x.user_id === resendId)?.email ||
      "";
    let cancelled = false;
    (async () => {
      setActionError("");
      setActionLoading(resendId);
      try {
        const res = await api.post<{ token: string }>(
          `/admin/users/${resendId}/resend-invite`,
          {}
        );
        const url = buildAppUrl("/activate", res.token);
        if (!cancelled) {
          setLinkDialog({
            type: "invite",
            url,
            userEmail: inviteeEmail || "Pending user",
          });
          const p = new URLSearchParams(window.location.search);
          p.delete("resendInvite");
          p.delete("inviteeEmail");
          const qs = p.toString();
          window.history.replaceState(
            null,
            "",
            qs ? `${window.location.pathname}?${qs}` : window.location.pathname
          );
        }
      } catch (err) {
        resendInviteHandledRef.current = false;
        if (!cancelled) {
          setActionError(
            err instanceof Error ? err.message : "Failed to resend invite"
          );
        }
      } finally {
        if (!cancelled) setActionLoading(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.role, loading, users, api, buildAppUrl]);

  useEffect(() => {
    if (!inviteOpen) return;
    if (user?.role === "hospital_admin") {
      fetchWards();
      fetchDepartments();
      fetchLabUnits();
    }
    if (user?.role === "super_admin" && inviteForm.hospital_id) {
      fetchWards();
      fetchDepartments();
      fetchLabUnits();
    }
  }, [inviteOpen, user?.role, inviteForm.hospital_id, fetchWards, fetchDepartments, fetchLabUnits]);

  useEffect(() => {
    if (user?.role === "hospital_admin" || (user?.role === "super_admin" && inviteForm.hospital_id)) {
      fetchDepartments();
      fetchLabUnits();
    }
  }, [user?.role, inviteForm.hospital_id, fetchDepartments, fetchLabUnits]);

  const handleCreateDefaultWorkflow = async () => {
    if (user?.role !== "hospital_admin" && user?.role !== "super_admin") return;
    const hospitalId = user?.role === "super_admin" ? inviteForm.hospital_id : undefined;
    if (user?.role === "super_admin" && !hospitalId) return;
    setSetupLoading(true);
    try {
      const defaultDepts = ["OPD", "Neuro", "Pediatrics", "Surgery", "Laboratory", "Radiology", "Emergency"];
      for (const name of defaultDepts) {
        await api.post("/admin/departments/create", user?.role === "super_admin" ? { name, hospital_id: hospitalId } : { name });
      }
      const defaultUnits = ["Hematology", "Chemistry", "Microbiology"];
      for (const name of defaultUnits) {
        await api.post("/admin/lab-units/create", user?.role === "super_admin" ? { name, hospital_id: hospitalId } : { name });
      }
      fetchDepartments();
      fetchLabUnits();
      setSetupDone(true);
    } catch {
      //
    } finally {
      setSetupLoading(false);
    }
  };

  const isSuperAdmin = user?.role === "super_admin";
  const needsWorkflowSetup = !isSuperAdmin && (departments.length === 0 || labUnits.length === 0);

  // Gate access to admin users page
  const adminRoles = ["hospital_admin", "super_admin"];
  if (user && !adminRoles.includes(user.role)) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <div className="text-center">
          <h2 className="text-lg font-semibold text-[#0F172A]">Access Denied</h2>
          <p className="mt-2 text-sm text-[#64748B]">You do not have permission to access this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {needsWorkflowSetup && (
        <Card className="border-[#0EAFBE]/30 bg-[#F0FDFF] p-4">
          <p className="text-sm font-medium text-[#0F172A]">Workflow setup</p>
          <p className="mt-1 text-sm text-[#64748B]">
            Create departments (OPD, Neuro, Pediatrics, etc.) and lab units (Hematology, Chemistry, Microbiology) so you can assign staff and route patients correctly.
          </p>
          <Button
            className="mt-3"
            variant="secondary"
            disabled={setupLoading}
            onClick={handleCreateDefaultWorkflow}
          >
            {setupLoading ? "Creating…" : "Create default departments and lab units"}
          </Button>
          {setupDone && <p className="mt-2 text-xs text-[#0EAFBE]">Done. Refresh the invite form if it is open.</p>}
        </Card>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
            {isSuperAdmin ? "Hospital Admin Management" : `Staff User Management — ${user?.hospital_name ?? "Hospital"}`}
          </h1>
          {isSuperAdmin && (
            <p className="mt-1 text-sm text-[#64748B]">
              Create hospital administrators only. Doctors, nurses, receptionists and lab staff are invited by each hospital&apos;s admin.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setInviteOpen(true)}>
            {isSuperAdmin ? "Create Hospital Admin" : "Invite New User"}
          </Button>
          {!isSuperAdmin && (
            <Button variant="secondary" onClick={() => setBulkOpen(true)}>Bulk CSV Import</Button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-4 py-2 text-sm text-[#DC2626]">
          {actionError}
        </div>
      )}
      <Card className="p-6">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#E2E8F0]">
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Name</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Email</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Role</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Department / Unit</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">GMDC Licence</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Status</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[#64748B]">Loading...</td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[#64748B]">No users.</td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.user_id} className="border-b border-[#F1F5F9]">
                    <td className="px-4 py-2">{u.full_name}</td>
                    <td className="px-4 py-2">{u.email}</td>
                    <td className="px-4 py-2">
                      <span className="rounded-full bg-[#F1F5F9] px-2 py-0.5 text-xs">{u.role}</span>
                    </td>
                    <td className="px-4 py-2 text-sm text-[#475569]">
                      {u.department_name ?? u.ward_name ?? u.lab_unit_name ?? "—"}
                    </td>
                    <td className="px-4 py-2">{u.role === "doctor" ? (u.gmdc_licence_number ?? "—") : "—"}</td>
                    <td className="px-4 py-2">{u.account_status}</td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {u.account_status === "pending" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={actionLoading !== null}
                            onClick={() => handleResendInvite({ user_id: u.user_id, email: u.email })}
                          >
                            {actionLoading === u.user_id ? "..." : "Resend invite"}
                          </Button>
                        )}
                        {u.account_status === "active" && (
                          <>
                            {user?.role === "hospital_admin" &&
                              ["doctor", "nurse", "receptionist", "lab_technician"].includes(u.role) && (
                              <div className="flex items-center gap-1">
                                <select
                                  className="h-8 rounded border border-[#CBD5E1] px-2 text-xs"
                                  value={u.role}
                                  onChange={(e) => {
                                    const nextRole = e.target.value as StaffRole;
                                    const fromRole = u.role as StaffRole;
                                    if (nextRole === fromRole) return;
                                    setRoleChangeTarget({
                                      user_id: u.user_id,
                                      full_name: u.full_name,
                                      fromRole,
                                      toRole: nextRole,
                                    });
                                    setRoleChangeConfirmOpen(true);
                                  }}
                                >
                                  <option value="doctor">Doctor</option>
                                  <option value="nurse">Nurse</option>
                                  <option value="receptionist">Receptionist</option>
                                  <option value="lab_technician">Lab Technician</option>
                                </select>
                              </div>
                            )}
                            <Button
                              size="sm"
                              variant="secondary"
                              disabled={actionLoading !== null}
                              onClick={() => {
                                setPasswordResetTarget({ user_id: u.user_id, email: u.email });
                                setPasswordResetConfirmOpen(true);
                              }}
                            >
                              {actionLoading === u.user_id ? "..." : "Send reset"}
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              disabled={actionLoading !== null}
                              onClick={() => handleResetMfa({ user_id: u.user_id })}
                            >
                              {actionLoading === u.user_id ? "..." : "Reset MFA"}
                            </Button>
                            <AdminPasskeyManagement
                              userId={u.user_id}
                              userName={u.full_name}
                              userEmail={u.email}
                              onResetComplete={() => {
                                // Optional: show success message or refresh
                              }}
                            />
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <SlideOver open={inviteOpen} onOpenChange={setInviteOpen} title={isSuperAdmin ? "Create Hospital Admin" : "Invite User"}>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setInviteError("");
            setInviteLoading(true);
            try {
              const body: Record<string, unknown> = isSuperAdmin
                ? {
                    full_name: inviteForm.full_name,
                    email: inviteForm.email,
                    role: "hospital_admin",
                    hospital_id: inviteForm.hospital_id,
                  }
                : {
                    full_name: inviteForm.full_name,
                    email: inviteForm.email,
                    role: inviteForm.role,
                    department_id: inviteForm.department_id || undefined,
                    ward_id: inviteForm.ward_id || undefined,
                    lab_unit_id: inviteForm.role === "lab_technician" ? (inviteForm.lab_unit_id || undefined) : undefined,
                    gmdc_licence_number: inviteForm.role === "doctor" ? inviteForm.gmdc_licence_number : undefined,
                  };
              await api.post("/admin/users/invite", body);
              fetch();
              setInviteOpen(false);
              setInviteForm(initialInviteForm);
            } catch (err) {
              setInviteError(err instanceof Error ? err.message : "Failed to invite");
            } finally {
              setInviteLoading(false);
            }
          }}
        >
          <Input
            label="Full Name"
            value={inviteForm.full_name}
            onChange={(e) => setInviteForm((f) => ({ ...f, full_name: e.target.value }))}
          />
          <Input
            label="Work Email"
            type="email"
            value={inviteForm.email}
            onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
          />
          {isSuperAdmin && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase text-[#64748B]">Hospital</label>
              <select
                value={inviteForm.hospital_id}
                onChange={(e) => setInviteForm((f) => ({ ...f, hospital_id: e.target.value }))}
                className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                required
              >
                <option value="">Select hospital</option>
                {facilities.map((f) => (
                  <option key={f.facility_id} value={f.facility_id}>{f.name}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-[#64748B]">This admin will manage only this facility.</p>
            </div>
          )}
          {!isSuperAdmin && (
            <>
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase text-[#64748B]">Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm((f) => ({ ...f, role: e.target.value as StaffRole }))}
                  className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                >
                  <option value="doctor">Doctor</option>
                  <option value="nurse">Nurse</option>
                  <option value="receptionist">Receptionist</option>
                  <option value="lab_technician">Lab Technician</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase text-[#64748B]">Department / Unit</label>
                <select
                  value={inviteForm.department_id}
                  onChange={(e) => setInviteForm((f) => ({ ...f, department_id: e.target.value }))}
                  className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                >
                  <option value="">Select department</option>
                  {departments.map((d) => (
                    <option key={d.department_id} value={d.department_id}>{d.name}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-[#64748B]">Assign staff to a department so work is routed to the correct team.</p>
              </div>
              {inviteForm.role === "nurse" && (
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase text-[#64748B]">Ward</label>
                  <select
                    value={inviteForm.ward_id}
                    onChange={(e) => setInviteForm((f) => ({ ...f, ward_id: e.target.value }))}
                    className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                  >
                    <option value="">Select ward</option>
                    {wards.map((w) => (
                      <option key={w.ward_id} value={w.ward_id}>{w.ward_name}</option>
                    ))}
                  </select>
                </div>
              )}
              {inviteForm.role === "lab_technician" && (
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase text-[#64748B]">Lab Unit (service tag)</label>
                  <select
                    value={inviteForm.lab_unit_id}
                    onChange={(e) => setInviteForm((f) => ({ ...f, lab_unit_id: e.target.value }))}
                    className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                  >
                    <option value="">Select lab unit</option>
                    {labUnits.map((u) => (
                      <option key={u.lab_unit_id} value={u.lab_unit_id}>{u.name}</option>
                    ))}
                  </select>
                  <p className="mt-1 text-xs text-[#64748B]">Technician will only see orders for this unit (e.g. Hematology, Chemistry).</p>
                </div>
              )}
              {inviteForm.role === "doctor" && (
                <Input
                  label="GMDC Licence Number"
                  value={inviteForm.gmdc_licence_number}
                  onChange={(e) => setInviteForm((f) => ({ ...f, gmdc_licence_number: e.target.value }))}
                  placeholder="GMDC-2018-04821"
                />
              )}
            </>
          )}
          {inviteError && <p className="text-sm text-[#DC2626]">{inviteError}</p>}
          <Button
            type="submit"
            className="w-full"
            disabled={inviteLoading || (isSuperAdmin && !inviteForm.hospital_id)}
          >
            {inviteLoading ? "Sending..." : isSuperAdmin ? "Create Hospital Admin" : "Send Invitation"}
          </Button>
        </form>
      </SlideOver>

      <SlideOver open={bulkOpen} onOpenChange={(open) => { setBulkOpen(open); if (!open) setBulkResult(null); setBulkFile(null); }} title="Bulk CSV Import">
        <p className="mb-3 text-sm text-[#64748B]">
          CSV columns: email, full_name, role (doctor|nurse|receptionist|lab_technician), department, ward_id, gmdc_licence_number (for doctors).
        </p>
        {user?.role === "super_admin" && (
          <div className="mb-4">
            <Input
              label="Hospital ID"
              value={bulkHospitalId}
              onChange={(e) => setBulkHospitalId(e.target.value)}
              placeholder="UUID of hospital"
            />
          </div>
        )}
        <input
          type="file"
          accept=".csv"
          className="mb-4 block w-full text-sm"
          onChange={(e) => setBulkFile(e.target.files?.[0] ?? null)}
        />
        {bulkResult && (
          <div className="mb-4 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-sm">
            <p className="font-medium text-[#0F172A]">Created: {bulkResult.created}</p>
            {bulkResult.errors.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-[#DC2626]">
                {bulkResult.errors.slice(0, 10).map((err, i) => (
                  <li key={i}>Row {err.row}: {err.error}</li>
                ))}
                {bulkResult.errors.length > 10 && <li>… and {bulkResult.errors.length - 10} more</li>}
              </ul>
            )}
          </div>
        )}
        <Button
          disabled={!bulkFile || bulkLoading}
          onClick={async () => {
            if (!bulkFile) return;
            setBulkLoading(true);
            setBulkResult(null);
            try {
              const form = new FormData();
              form.append("file", bulkFile);
              if (user?.role === "super_admin" && bulkHospitalId) form.append("hospital_id", bulkHospitalId);
              const res = await api.postForm<{ created: number; errors?: Array<{ row: number; error: string }> }>("/admin/users/bulk-import", form);
              setBulkResult({ created: res.created, errors: res.errors ?? [] });
              if (res.created > 0) fetch();
            } catch (err) {
              setBulkResult({ created: 0, errors: [{ row: 0, error: err instanceof Error ? err.message : "Upload failed" }] });
            } finally {
              setBulkLoading(false);
            }
          }}
        >
          {bulkLoading ? "Importing..." : "Upload CSV"}
        </Button>
      </SlideOver>

      <Dialog open={!!linkDialog} onOpenChange={(open) => !open && setLinkDialog(null)}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogClose />
            <DialogHeader>
              <DialogTitle>
                {linkDialog?.type === "reset" ? "Password reset link" : "Activation link"}
              </DialogTitle>
            </DialogHeader>
            <p className="mb-2 text-sm text-[#64748B]">
              Send this link to {linkDialog?.userEmail ?? "the user"} (e.g. by email). Link is single-use and time-limited.
            </p>
            <div className="flex gap-2">
              <input
                readOnly
                value={linkDialog?.url ?? ""}
                className="flex-1 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-sm text-[#0F172A]"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  if (linkDialog?.url) navigator.clipboard.writeText(linkDialog.url);
                }}
              >
                Copy
              </Button>
            </div>
            <Button className="mt-4 w-full" onClick={() => setLinkDialog(null)}>
              Done
            </Button>
          </DialogContent>
        </DialogPortal>
      </Dialog>

      <ConfirmDialog
        open={passwordResetConfirmOpen}
        onOpenChange={(open) => {
          setPasswordResetConfirmOpen(open);
          if (!open) setPasswordResetTarget(null);
        }}
        title="Send password reset email?"
        message="This will send a password reset email to the selected user. They will be asked to set a new password before logging in again."
        confirmLabel="Send reset email"
        variant="danger"
        loading={!!(passwordResetTarget && actionLoading === passwordResetTarget.user_id)}
        onConfirm={async () => {
          if (!passwordResetTarget) return;
          await handleSendPasswordReset(passwordResetTarget);
        }}
      />
      <ConfirmDialog
        open={roleChangeConfirmOpen}
        onOpenChange={(open) => {
          setRoleChangeConfirmOpen(open);
          if (!open) setRoleChangeTarget(null);
        }}
        title="Confirm role change"
        message={
          roleChangeTarget
            ? roleImpactMessage(roleChangeTarget.full_name, roleChangeTarget.fromRole, roleChangeTarget.toRole)
            : "Confirm role change?"
        }
        confirmLabel="Confirm role change"
        variant="danger"
        loading={!!(roleChangeTarget && actionLoading === roleChangeTarget.user_id)}
        onConfirm={handleRoleChange}
      />
    </div>
  );
}
