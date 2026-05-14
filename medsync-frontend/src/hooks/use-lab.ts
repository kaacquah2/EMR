"use client";
import { useState } from "react";
import useSWR from "swr";
import { useApi } from "./use-api";
import { useAuth } from "@/lib/auth-context";
import { useHospitalWS } from "./use-hospital-ws";

export interface LabOrderItem {
  id: string;
  patient_name: string;
  patient_age: number | null;
  patient_gender: string | null;
  gha_id: string;
  test_name: string;
  ordering_doctor_name: string;
  ordered_at: string;
  urgency: "stat" | "urgent" | "routine";
  urgency_rank: number;
  status: string;
  collection_time?: string | null;
  lab_unit_id?: string | null;
  tat_target_minutes: number;
  minutes_remaining: number | null;
}

export interface LabOrdersResponse {
  count: number;
  limit: number;
  offset: number;
  tab: string;
  stats: {
    stat_orders: number;
    urgent_orders: number;
    routine_orders: number;
    in_progress_orders: number;
  };
  data: LabOrderItem[];
}

export interface LabResultItem {
  id: string;
  order_id: string;
  patient_name: string;
  gha_id: string;
  test_name: string;
  result_value: string;
  reference_range: string;
  status: string;
  lab_tech_name: string;
  created_at: string;
  attachment_url?: string;
}

export interface LabResultsResponse {
  count: number;
  limit: number;
  offset: number;
  data: LabResultItem[];
}


export function useLabOrders(tab: "all" | "pending" | "in_progress" | "resulted_today" | "verified") {
  const api = useApi();
  const { user } = useAuth();
  
  const { data, error, isLoading, mutate } = useSWR<{ data: LabOrdersResponse }>(
    [`/lab/orders`, tab],
    ([url]) => api.get<{ data: LabOrdersResponse }>(`${url}?tab=${tab}&ordering=urgency_rank,created_at`),
    {
      revalidateOnFocus: true,
      dedupingInterval: 30000,
    }
  );

  // Listen for real-time lab updates
  useHospitalWS(user?.hospital_id, (event) => {
    if (event.type === "lab_event") {
      mutate();
    }
  });

  return { 
    orders: data?.data?.data || [], 
    stats: data?.data?.stats || { stat_orders: 0, urgent_orders: 0, routine_orders: 0, in_progress_orders: 0 },
    loading: isLoading, 
    error: error?.message || null, 
    fetch: mutate 
  };
}

export function useLabResults(filters?: { status?: string[]; date_from?: string; date_to?: string }) {
  const api = useApi();
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, error, isLoading, mutate } = useSWR<{ data: LabResultsResponse }>(
    [`/lab/results`, filters, offset],
    () => {
      const params = new URLSearchParams();
      params.set("limit", limit.toString());
      params.set("offset", offset.toString());
      if (filters?.status?.length) params.set("status", filters.status.join(","));
      if (filters?.date_from) params.set("date_from", filters.date_from);
      if (filters?.date_to) params.set("date_to", filters.date_to);
      return api.get<{ data: LabResultsResponse }>(`/lab/results?${params.toString()}`);
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 30000,
    }
  );

  // Listen for real-time lab updates
  useHospitalWS(user?.hospital_id, (event) => {
    if (event.type === "lab_event") {
      mutate();
    }
  });

  return { 
    results: data?.data?.data || [], 
    total: data?.data?.count || 0, 
    loading: isLoading, 
    error: error?.message || null, 
    limit, 
    offset, 
    setOffset, 
    fetch: mutate 
  };
}

