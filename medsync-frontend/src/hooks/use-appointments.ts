"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";

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
  const api = useApi();
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (patientId) params.set("patient_id", patientId);
      if (statusFilter) params.set("status", statusFilter);
      if (departmentId) params.set("department_id", departmentId);
      const data = await api.get<{ data: AppointmentItem[] }>(`/appointments?${params}`);
      setAppointments(data.data || []);
    } catch {
      setAppointments([]);
    } finally {
      setLoading(false);
    }
  }, [api, date, patientId, statusFilter, departmentId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { appointments, loading, fetch };
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
