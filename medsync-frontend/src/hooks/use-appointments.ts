"use client";

import { useState, useCallback } from "react";
import { useApi } from "./use-api";
import { useResource } from "./use-resource";

export interface AppointmentItem {
  id: string;
  patient_id: string;
  patient_name: string;
  ghana_health_id: string;
  scheduled_at: string;
  status: string;
  appointment_type: string;
  provider_name: string | null;
  notes: string | null;
}

export function useAppointments(
  date?: string,
  patientId?: string,
  statusFilter?: string,
  departmentId?: string
) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (patientId) params.set("patient_id", patientId);
  if (statusFilter) params.set("status", statusFilter);
  if (departmentId) params.set("department_id", departmentId);
  const paramsStr = params.toString();
  const path = `/appointments${paramsStr ? `?${paramsStr}` : ""}`;

  const { data, loading, refetch } = useResource<{ data: AppointmentItem[] }>(path);

  // Wrap to return void — some consumers (e.g. AppointmentBulkActions) expect () => Promise<void>.
  const fetch = useCallback(async () => { await refetch(); }, [refetch]);

  return { appointments: data?.data ?? [], loading, fetch };
}

export function useCreateAppointment() {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const create = useCallback(
    async (body: {
      patient_id: string;
      appointment_date?: string;
      scheduled_at?: string;
      department_id?: string;
      doctor_id?: string;
      appointment_type?: string;
      provider_id?: string;
      notes?: string;
      hospital_id?: string;
    }) => {
      setLoading(true);
      try {
        const data = await api.post<{ id: string }>("/appointments/create", body);
        return data;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { create, loading };
}

export function useUpdateAppointment(id: string | null) {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const update = useCallback(
    async (body: { status?: string; scheduled_at?: string; notes?: string }) => {
      if (!id) return;
      setLoading(true);
      try {
        await api.patch(`/appointments/${id}`, body);
      } finally {
        setLoading(false);
      }
    },
    [api, id]
  );

  return { update, loading };
}

export interface BulkAppointmentItem {
  patient_id: string;
  scheduled_at: string;
  department_id?: string;
  doctor_id?: string;
  appointment_type?: string;
  notes?: string;
}

export interface BulkImportResponse {
  created: number;
  failed: number;
  details: Array<{
    row_num?: number;
    status: string;
    message: string;
    appointment_id?: string;
    patient_id?: string;
  }>;
}

export function useBulkImportAppointments() {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const submit = useCallback(
    async (appointments: BulkAppointmentItem[]): Promise<BulkImportResponse> => {
      setLoading(true);
      try {
        const response = await api.post<BulkImportResponse>(
          "/appointments/bulk-import",
          { appointments }
        );
        return response;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { submit, loading };
}
