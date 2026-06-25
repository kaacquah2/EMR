"use client";

import { useState, useCallback } from "react";
import { useApi } from "./use-api";
import { useResource } from "./use-resource";
import type { User } from "@/lib/types";

// ─── Auto-fetching hooks (migrated to useResource) ───────────────────────────

export function useUsers(role?: string, status?: string) {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  if (status) params.set("account_status", status);
  const paramsStr = params.toString();
  const path = `/admin/users${paramsStr ? `?${paramsStr}` : ""}`;

  const { data, loading, error, refetch } = useResource<{ data: User[] }>(path);
  return { users: data?.data ?? [], loading, error, fetch: refetch };
}

export interface AuditLogFilters {
  action?: string;
  date_from?: string;
  date_to?: string;
}

export function useAuditLogs(filters?: AuditLogFilters) {
  const params = new URLSearchParams();
  if (filters?.action) params.set("action", filters.action);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  const paramsStr = params.toString();
  const path = paramsStr ? `/admin/audit-logs?${paramsStr}` : "/admin/audit-logs";

  const { data, loading, error, refetch } = useResource<{
    data: Array<{
      log_id: string;
      user: string;
      action: string;
      resource_type?: string;
      timestamp: string;
      ip_address?: string;
      hospital?: string | null;
    }>;
  }>(path);
  return { logs: data?.data ?? [], loading, error, fetch: refetch };
}

export interface Bed {
  id: string;
  bed_code: string;
  status: string;
  ward_id: string;
  ward_name: string;
}

export function useBedsByWard(wardId: string | null) {
  const path = wardId ? `/admin/wards/${wardId}/beds?status=available` : null;
  const { data, loading, error, refetch } = useResource<{ data: Bed[] }>(path);
  return { beds: data?.data ?? [], loading, error, fetch: refetch };
}

// ─── On-demand hooks (manual fetch — no auto-fetch useEffect needed) ─────────

export function useWards(hospitalId?: string | null) {
  const api = useApi();
  const [wards, setWards] = useState<Array<{ ward_id: string; ward_name: string; ward_type: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ ward_id: string; ward_name: string; ward_type: string }> }>(`/admin/wards${params}`);
      setWards(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load wards");
      setWards([]);
    } finally {
      setLoading(false);
    }
  }, [api, hospitalId]);

  return { wards, error, loading, fetch };
}

export function useDepartments(hospitalId?: string | null) {
  const api = useApi();
  const [departments, setDepartments] = useState<Array<{ department_id: string; name: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ department_id: string; name: string }> }>(`/admin/departments${params}`);
      setDepartments(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load departments");
      setDepartments([]);
    } finally {
      setLoading(false);
    }
  }, [api, hospitalId]);

  return { departments, error, loading, fetch };
}

export function useLabUnits(hospitalId?: string | null) {
  const api = useApi();
  const [labUnits, setLabUnits] = useState<Array<{ lab_unit_id: string; name: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ lab_unit_id: string; name: string }> }>(`/admin/lab-units${params}`);
      setLabUnits(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lab units");
      setLabUnits([]);
    } finally {
      setLoading(false);
    }
  }, [api, hospitalId]);

  return { labUnits, error, loading, fetch };
}

export function useLabTestTypes(hospitalId?: string | null) {
  const api = useApi();
  const [labTestTypes, setLabTestTypes] = useState<Array<{ test_name: string; lab_unit_id: string; lab_unit_name: string; specimen: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ test_name: string; lab_unit_id: string; lab_unit_name: string; specimen: string }> }>(`/admin/lab-test-types${params}`);
      setLabTestTypes(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lab test types");
      setLabTestTypes([]);
    } finally {
      setLoading(false);
    }
  }, [api, hospitalId]);

  return { labTestTypes, error, loading, fetch };
}

export function useDoctors(departmentId?: string | null, hospitalId?: string | null) {
  const api = useApi();
  const [doctors, setDoctors] = useState<Array<{ user_id: string; full_name: string; department_id: string | null; department_name: string | null }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams();
      if (departmentId) p.set("department_id", departmentId);
      if (hospitalId) p.set("hospital_id", hospitalId);
      const q = p.toString() ? `?${p.toString()}` : "";
      const data = await api.get<{ data: Array<{ user_id: string; full_name: string; department_id: string | null; department_name: string | null }> }>(`/admin/doctors${q}`);
      setDoctors(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load doctors");
      setDoctors([]);
    } finally {
      setLoading(false);
    }
  }, [api, departmentId, hospitalId]);

  return { doctors, error, loading, fetch };
}
