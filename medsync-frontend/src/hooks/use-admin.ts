"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import type { User } from "@/lib/types";

export function useUsers(role?: string, status?: string) {
  const api = useApi();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (role) params.set("role", role);
      if (status) params.set("account_status", status);
      const data = await api.get<{ data: User[] }>(`/admin/users?${params}`);
      setUsers(data.data || []);
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [api, role, status]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { users, loading, fetch };
}

export interface AuditLogFilters {
  action?: string;
  date_from?: string;
  date_to?: string;
}

export function useAuditLogs(filters?: AuditLogFilters) {
  const api = useApi();
  const [logs, setLogs] = useState<
    Array<{
      log_id: string;
      user: string;
      action: string;
      resource_type?: string;
      timestamp: string;
      ip_address?: string;
      hospital?: string | null;
    }>
  >([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters?.action) params.set("action", filters.action);
      if (filters?.date_from) params.set("date_from", filters.date_from);
      if (filters?.date_to) params.set("date_to", filters.date_to);
      const qs = params.toString();
      const url = qs ? `/admin/audit-logs?${qs}` : "/admin/audit-logs";
      const data = await api.get<{
        data: Array<{
          log_id: string;
          user: string;
          action: string;
          resource_type?: string;
          timestamp: string;
          ip_address?: string;
          hospital?: string | null;
        }>;
      }>(url);
      setLogs(data.data || []);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [api, filters?.action, filters?.date_from, filters?.date_to]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { logs, loading, fetch };
}

export function useWards(hospitalId?: string | null) {
  const api = useApi();
  const [wards, setWards] = useState<Array<{ ward_id: string; ward_name: string; ward_type: string }>>([]);

  const fetch = useCallback(async () => {
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ ward_id: string; ward_name: string; ward_type: string }> }>(`/admin/wards${params}`);
      setWards(data.data || []);
    } catch {
      setWards([]);
    }
  }, [api, hospitalId]);

  return { wards, fetch };
}

export interface Bed {
  id: string;
  bed_code: string;
  status: string;
  ward_id: string;
  ward_name: string;
}

export function useBedsByWard(wardId: string | null) {
  const api = useApi();
  const [beds, setBeds] = useState<Bed[]>([]);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    if (!wardId) {
      setBeds([]);
      return;
    }
    setLoading(true);
    try {
      const data = await api.get<{ data: Bed[] }>(`/admin/wards/${wardId}/beds?status=available`);
      setBeds(data.data || []);
    } catch {
      setBeds([]);
    } finally {
      setLoading(false);
    }
  }, [api, wardId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { beds, loading, fetch };
}

export function useDepartments(hospitalId?: string | null) {
  const api = useApi();
  const [departments, setDepartments] = useState<Array<{ department_id: string; name: string }>>([]);

  const fetch = useCallback(async () => {
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ department_id: string; name: string }> }>(`/admin/departments${params}`);
      setDepartments(data.data || []);
    } catch {
      setDepartments([]);
    }
  }, [api, hospitalId]);

  return { departments, fetch };
}

export function useLabUnits(hospitalId?: string | null) {
  const api = useApi();
  const [labUnits, setLabUnits] = useState<Array<{ lab_unit_id: string; name: string }>>([]);

  const fetch = useCallback(async () => {
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ lab_unit_id: string; name: string }> }>(`/admin/lab-units${params}`);
      setLabUnits(data.data || []);
    } catch {
      setLabUnits([]);
    }
  }, [api, hospitalId]);

  return { labUnits, fetch };
}

export function useLabTestTypes(hospitalId?: string | null) {
  const api = useApi();
  const [labTestTypes, setLabTestTypes] = useState<Array<{ test_name: string; lab_unit_id: string; lab_unit_name: string; specimen: string }>>([]);

  const fetch = useCallback(async () => {
    try {
      const params = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : "";
      const data = await api.get<{ data: Array<{ test_name: string; lab_unit_id: string; lab_unit_name: string; specimen: string }> }>(`/admin/lab-test-types${params}`);
      setLabTestTypes(data.data || []);
    } catch {
      setLabTestTypes([]);
    }
  }, [api, hospitalId]);

  return { labTestTypes, fetch };
}

export function useDoctors(departmentId?: string | null, hospitalId?: string | null) {
  const api = useApi();
  const [doctors, setDoctors] = useState<Array<{ user_id: string; full_name: string; department_id: string | null; department_name: string | null }>>([]);

  const fetch = useCallback(async () => {
    try {
      const p = new URLSearchParams();
      if (departmentId) p.set("department_id", departmentId);
      if (hospitalId) p.set("hospital_id", hospitalId);
      const q = p.toString() ? `?${p.toString()}` : "";
      const data = await api.get<{ data: Array<{ user_id: string; full_name: string; department_id: string | null; department_name: string | null }> }>(`/admin/doctors${q}`);
      setDoctors(data.data || []);
    } catch {
      setDoctors([]);
    }
  }, [api, departmentId, hospitalId]);

  return { doctors, fetch };
}
