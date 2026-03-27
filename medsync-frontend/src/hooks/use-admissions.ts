"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";

export interface Admission {
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

export function useAdmissions() {
  const api = useApi();
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ data: Admission[] }>("/admissions");
      setAdmissions(data.data || []);
    } catch {
      setAdmissions([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { admissions, loading, fetch };
}
