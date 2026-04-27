"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";

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
  const [orders, setOrders] = useState<LabOrderItem[]>([]);
  const [stats, setStats] = useState<LabOrdersResponse["stats"]>({
    stat_orders: 0,
    urgent_orders: 0,
    routine_orders: 0,
    in_progress_orders: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<LabOrdersResponse>(`/lab/orders?tab=${tab}&ordering=urgency_rank,created_at`);
      setOrders(data.data || []);
      setStats(data.stats || { stat_orders: 0, urgent_orders: 0, routine_orders: 0, in_progress_orders: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lab orders");
      setOrders([]);
      setStats({ stat_orders: 0, urgent_orders: 0, routine_orders: 0, in_progress_orders: 0 });
    } finally {
      setLoading(false);
    }
  }, [api, tab]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { orders, stats, loading, error, fetch };
}

export function useLabResults(filters?: { status?: string[]; date_from?: string; date_to?: string }) {
  const api = useApi();
  const [results, setResults] = useState<LabResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  const fetch = useCallback(
    async (newOffset: number = 0) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("limit", limit.toString());
        params.set("offset", newOffset.toString());

        if (filters?.status?.length) {
          params.set("status", filters.status.join(","));
        }
        if (filters?.date_from) {
          params.set("date_from", filters.date_from);
        }
        if (filters?.date_to) {
          params.set("date_to", filters.date_to);
        }

        const data = await api.get<LabResultsResponse>(`/lab/results?${params.toString()}`);
        setResults(data.data || []);
        setTotal(data.count || 0);
        setOffset(newOffset);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load lab results");
        setResults([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [api, filters, limit]
  );

  useEffect(() => {
    fetch(0);
  }, [fetch]);

  return { results, total, loading, error, limit, offset, setOffset, fetch };
}

