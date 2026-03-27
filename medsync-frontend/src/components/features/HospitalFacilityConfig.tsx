"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/use-api";
import { useDepartments, useLabUnits, useLabTestTypes } from "@/hooks/use-admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

const WARD_TYPES = [
  { v: "general", l: "General" },
  { v: "icu", l: "ICU" },
  { v: "maternity", l: "Maternity" },
  { v: "paediatric", l: "Paediatric" },
  { v: "surgical", l: "Surgical" },
  { v: "emergency", l: "Emergency" },
  { v: "other", l: "Other" },
];

type WardRow = { ward_id: string; ward_name: string; ward_type: string };

export function HospitalFacilityConfig() {
  const api = useApi();
  const { departments, fetch: fetchDepts } = useDepartments();
  const { labUnits, fetch: fetchLabs } = useLabUnits();
  const { labTestTypes, fetch: fetchTests } = useLabTestTypes();
  const [tab, setTab] = useState<"wards" | "beds" | "departments" | "labs" | "tests">("wards");
  const [wards, setWards] = useState<WardRow[]>([]);
  const [wardLoading, setWardLoading] = useState(true);
  const [newWard, setNewWard] = useState({ name: "", ward_type: "general" });
  const [bulkWardId, setBulkWardId] = useState("");
  const [bulkCount, setBulkCount] = useState("5");
  const [newDept, setNewDept] = useState("");
  const [newLab, setNewLab] = useState("");
  const [testForm, setTestForm] = useState({ lab_unit_id: "", test_name: "", specimen: "" });

  const loadWards = useCallback(async () => {
    setWardLoading(true);
    try {
      const r = await api.get<{ data: WardRow[] }>("/admin/wards?include_inactive=true");
      setWards(Array.isArray(r?.data) ? r.data : []);
    } catch {
      setWards([]);
    } finally {
      setWardLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void loadWards();
  }, [loadWards]);

  useEffect(() => {
    void fetchDepts();
    void fetchLabs();
    void fetchTests();
  }, [fetchDepts, fetchLabs, fetchTests]);

  const addWard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWard.name.trim()) return;
    await api.post("/admin/wards/create", { name: newWard.name.trim(), ward_type: newWard.ward_type });
    setNewWard({ name: "", ward_type: "general" });
    await loadWards();
  };

  const bulkBeds = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkWardId) return;
    const n = parseInt(bulkCount, 10);
    if (!Number.isFinite(n) || n < 1) return;
    await api.post(`/admin/wards/${bulkWardId}/beds/bulk`, { count: n });
    await loadWards();
  };

  const addDept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDept.trim()) return;
    await api.post("/admin/departments/create", { name: newDept.trim() });
    setNewDept("");
    await fetchDepts();
  };

  const addLab = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLab.trim()) return;
    await api.post("/admin/lab-units/create", { name: newLab.trim() });
    setNewLab("");
    await fetchLabs();
  };

  const addTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testForm.lab_unit_id || !testForm.test_name.trim()) return;
    await api.post("/admin/lab-test-types/create", {
      lab_unit_id: testForm.lab_unit_id,
      test_name: testForm.test_name.trim(),
      specimen: testForm.specimen.trim(),
    });
    setTestForm({ lab_unit_id: testForm.lab_unit_id, test_name: "", specimen: "" });
    await fetchTests();
  };

  const tabs: { id: typeof tab; label: string }[] = [
    { id: "wards", label: "Wards" },
    { id: "beds", label: "Beds" },
    { id: "departments", label: "Departments" },
    { id: "labs", label: "Lab units" },
    { id: "tests", label: "Lab test types" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2 border-b border-[#E2E8F0] pb-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={
              "rounded-lg px-4 py-2 text-sm font-medium " +
              (tab === t.id ? "bg-[#0B8A96] text-white" : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "wards" && (
        <Card className="p-6">
          <h2 className="mb-4 font-sora text-lg font-semibold text-[#0F172A]">Wards</h2>
          <form onSubmit={addWard} className="mb-6 flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-[#64748B]">Name</label>
              <Input value={newWard.name} onChange={(e) => setNewWard((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs text-[#64748B]">Type</label>
              <select
                className="rounded-md border border-[#E2E8F0] px-2 py-2 text-sm"
                value={newWard.ward_type}
                onChange={(e) => setNewWard((f) => ({ ...f, ward_type: e.target.value }))}
              >
                {WARD_TYPES.map((w) => (
                  <option key={w.v} value={w.v}>
                    {w.l}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit">Add ward</Button>
          </form>
          {wardLoading ? (
            <p className="text-[#64748B]">Loading…</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="py-2 text-left">Name</th>
                  <th className="py-2 text-left">Type</th>
                </tr>
              </thead>
              <tbody>
                {wards.map((w) => (
                  <tr key={w.ward_id} className="border-b border-[#F1F5F9]">
                    <td className="py-2">{w.ward_name}</td>
                    <td className="py-2 text-[#64748B]">{w.ward_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {tab === "beds" && (
        <Card className="p-6">
          <h2 className="mb-4 font-sora text-lg font-semibold text-[#0F172A]">Bulk add beds</h2>
          <form onSubmit={bulkBeds} className="flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-[#64748B]">Ward</label>
              <select
                className="rounded-md border border-[#E2E8F0] px-2 py-2 text-sm"
                value={bulkWardId}
                onChange={(e) => setBulkWardId(e.target.value)}
              >
                <option value="">Select…</option>
                {wards.map((w) => (
                  <option key={w.ward_id} value={w.ward_id}>
                    {w.ward_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#64748B]">Count</label>
              <Input value={bulkCount} onChange={(e) => setBulkCount(e.target.value)} className="w-24" />
            </div>
            <Button type="submit">Add beds</Button>
          </form>
        </Card>
      )}

      {tab === "departments" && (
        <Card className="p-6">
          <h2 className="mb-4 font-sora text-lg font-semibold text-[#0F172A]">Departments</h2>
          <form onSubmit={addDept} className="mb-4 flex gap-2">
            <Input
              placeholder="Department name"
              value={newDept}
              onChange={(e) => setNewDept(e.target.value)}
              className="max-w-md"
            />
            <Button type="submit">Add</Button>
          </form>
          <ul className="list-disc space-y-1 pl-6 text-sm">
            {departments.map((d) => (
              <li key={d.department_id}>{d.name}</li>
            ))}
          </ul>
        </Card>
      )}

      {tab === "labs" && (
        <Card className="p-6">
          <h2 className="mb-4 font-sora text-lg font-semibold text-[#0F172A]">Lab units</h2>
          <form onSubmit={addLab} className="mb-4 flex gap-2">
            <Input
              placeholder="Lab unit name"
              value={newLab}
              onChange={(e) => setNewLab(e.target.value)}
              className="max-w-md"
            />
            <Button type="submit">Add</Button>
          </form>
          <ul className="list-disc space-y-1 pl-6 text-sm">
            {labUnits.map((u) => (
              <li key={u.lab_unit_id}>{u.name}</li>
            ))}
          </ul>
        </Card>
      )}

      {tab === "tests" && (
        <Card className="p-6">
          <h2 className="mb-4 font-sora text-lg font-semibold text-[#0F172A]">Lab test types</h2>
          <form onSubmit={addTest} className="mb-4 flex flex-wrap gap-2">
            <select
              className="rounded-md border border-[#E2E8F0] px-2 py-2 text-sm"
              value={testForm.lab_unit_id}
              onChange={(e) => setTestForm((f) => ({ ...f, lab_unit_id: e.target.value }))}
            >
              <option value="">Lab unit…</option>
              {labUnits.map((u) => (
                <option key={u.lab_unit_id} value={u.lab_unit_id}>
                  {u.name}
                </option>
              ))}
            </select>
            <Input
              placeholder="Test name"
              value={testForm.test_name}
              onChange={(e) => setTestForm((f) => ({ ...f, test_name: e.target.value }))}
            />
            <Input
              placeholder="Specimen (optional)"
              value={testForm.specimen}
              onChange={(e) => setTestForm((f) => ({ ...f, specimen: e.target.value }))}
            />
            <Button type="submit">Add test type</Button>
          </form>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0]">
                <th className="py-2 text-left">Test</th>
                <th className="py-2 text-left">Lab unit</th>
              </tr>
            </thead>
            <tbody>
              {labTestTypes.map((t, i) => (
                <tr key={`${t.test_name}-${i}`} className="border-b border-[#F1F5F9]">
                  <td className="py-2">{t.test_name}</td>
                  <td className="py-2 text-[#64748B]">{t.lab_unit_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
