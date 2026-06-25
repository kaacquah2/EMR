"use client";

import { useResource } from "./use-resource";

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
  const { data, loading, error, refetch } = useResource<{ data: Admission[] }>("/admissions");
  return {
    admissions: data?.data ?? [],
    loading,
    error,
    fetch: refetch,
  };
}
