"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter, useSearchParams } from "next/navigation";
import { useFacilities, useCreateFacility, useUpdateFacility } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Facility } from "@/lib/types";
import { HospitalFacilityConfig } from "@/components/features/HospitalFacilityConfig";

export default function AdminFacilitiesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const facilitiesSource =
    user?.role === "super_admin" ? "superadmin_hospitals" : "interop";
  const { facilities, loading, fetch } = useFacilities(facilitiesSource);
  const hasOpenedForHospital = useRef(false);
  const { create, loading: creating, error: createError } = useCreateFacility();
  const { update, loading: updating } = useUpdateFacility();

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editFacility, setEditFacility] = useState<Facility | null>(null);
  const [form, setForm] = useState({
    name: "",
    nhis_code: "",
    region: "",
    address: "",
    phone: "",
    email: "",
    head_of_facility: "",
  });
  const [editForm, setEditForm] = useState({
    name: "",
    region: "",
    nhis_code: "",
    address: "",
    phone: "",
    email: "",
    head_of_facility: "",
    is_active: true,
  });

  useEffect(() => {
    if (user?.role === "super_admin") fetch();
  }, [user?.role, fetch]);

  const hospitalId = searchParams.get("hospital");
  useEffect(() => {
    if (user?.role !== "super_admin" || !hospitalId || loading || facilities.length === 0 || hasOpenedForHospital.current) return;
    const f = facilities.find((x) => x.facility_id === hospitalId);
    if (f) {
      hasOpenedForHospital.current = true;
      queueMicrotask(() => {
        setEditFacility(f);
        setEditForm({
          name: f.name,
          region: f.region,
          nhis_code: f.nhis_code,
          address: f.address ?? "",
          phone: f.phone ?? "",
          email: f.email ?? "",
          head_of_facility: "",
          is_active: f.is_active ?? true,
        });
        setEditOpen(true);
      });
    }
  }, [user?.role, hospitalId, loading, facilities]);

  if (!user) return null;

  if (user.role === "hospital_admin") {
    return (
      <div className="space-y-6">
        <h1 className="font-sora text-3xl font-bold text-[#0F172A]">Facility config</h1>
        <HospitalFacilityConfig />
      </div>
    );
  }

  if (user.role !== "super_admin") {
    router.replace("/unauthorized");
    return null;
  }

  const openCreate = () => {
    setForm({ name: "", nhis_code: "", region: "", address: "", phone: "", email: "", head_of_facility: "" });
    setCreateOpen(true);
  };

  const openEdit = (f: Facility) => {
    setEditFacility(f);
    setEditForm({
      name: f.name,
      region: f.region,
      nhis_code: f.nhis_code,
      address: f.address ?? "",
      phone: f.phone ?? "",
      email: f.email ?? "",
      head_of_facility: "",
      is_active: f.is_active ?? true,
    });
    setEditOpen(true);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create({
        name: form.name.trim(),
        nhis_code: form.nhis_code.trim(),
        region: form.region.trim() || "Unknown",
        address: form.address.trim() || undefined,
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
        head_of_facility: form.head_of_facility.trim() || undefined,
      });
      setCreateOpen(false);
      fetch();
    } catch {
      // error in createError
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editFacility) return;
    try {
      await update(editFacility.facility_id, {
        name: editForm.name.trim(),
        region: editForm.region.trim(),
        nhis_code: editForm.nhis_code.trim(),
        address: editForm.address.trim() || undefined,
        phone: editForm.phone.trim() || undefined,
        email: editForm.email.trim() || undefined,
        head_of_facility: editForm.head_of_facility.trim() || undefined,
        is_active: editForm.is_active,
      });
      setEditOpen(false);
      setEditFacility(null);
      fetch();
    } catch {
      //
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-3xl font-bold text-[#0F172A]">Facilities</h1>
        <Button onClick={openCreate}>Add Facility</Button>
      </div>

      <Card className="p-6">
        {loading ? (
          <p className="text-[#64748B]">Loading...</p>
        ) : facilities.length === 0 ? (
          <p className="text-[#64748B]">No facilities. Add one to get started.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Name</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Region</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">NHIS Code</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-[#64748B]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {facilities.map((f) => (
                  <tr key={f.facility_id} className="border-b border-[#F1F5F9]">
                    <td className="px-4 py-2 font-medium">{f.name}</td>
                    <td className="px-4 py-2">{f.region}</td>
                    <td className="px-4 py-2">{f.nhis_code}</td>
                    <td className="px-4 py-2 text-right">
                      <Button variant="secondary" size="sm" onClick={() => openEdit(f)}>
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Facility</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-3">
              <label className="block text-sm font-medium text-[#0F172A]">Name *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
                required
                placeholder="Facility name"
              />
              <label className="block text-sm font-medium text-[#0F172A]">NHIS Code *</label>
              <Input
                value={form.nhis_code}
                onChange={(e) => setForm((s) => ({ ...s, nhis_code: e.target.value }))}
                required
                placeholder="NHIS code"
              />
              <label className="block text-sm font-medium text-[#0F172A]">Region</label>
              <Input
                value={form.region}
                onChange={(e) => setForm((s) => ({ ...s, region: e.target.value }))}
                placeholder="Region"
              />
              {createError && <p className="text-sm text-red-600">{createError}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={creating}>Create</Button>
              </div>
            </form>
          </DialogContent>
        </DialogPortal>
      </Dialog>

      <Dialog
        open={editOpen}
        onOpenChange={(open) => {
          if (!open) setEditFacility(null);
          setEditOpen(open);
        }}
      >
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Facility</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleUpdate} className="space-y-3">
              <label className="block text-sm font-medium text-[#0F172A]">Name</label>
              <Input
                value={editForm.name}
                onChange={(e) => setEditForm((s) => ({ ...s, name: e.target.value }))}
              />
              <label className="block text-sm font-medium text-[#0F172A]">NHIS Code</label>
              <Input
                value={editForm.nhis_code}
                onChange={(e) => setEditForm((s) => ({ ...s, nhis_code: e.target.value }))}
              />
              <label className="block text-sm font-medium text-[#0F172A]">Region</label>
              <Input
                value={editForm.region}
                onChange={(e) => setEditForm((s) => ({ ...s, region: e.target.value }))}
              />
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm((s) => ({ ...s, is_active: e.target.checked }))}
                />
                <span className="text-sm">Active</span>
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="secondary" onClick={() => setEditOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={updating}>Save</Button>
              </div>
            </form>
          </DialogContent>
        </DialogPortal>
      </Dialog>
    </div>
  );
}
