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

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<LabOrdersResponse>(`/lab/orders?tab=${tab}&ordering=urgency_rank,created_at`);
      setOrders(data.data || []);
      setStats(data.stats || { stat_orders: 0, urgent_orders: 0, routine_orders: 0, in_progress_orders: 0 });
    } catch {
      setOrders([]);
      setStats({ stat_orders: 0, urgent_orders: 0, routine_orders: 0, in_progress_orders: 0 });
    } finally {
      setLoading(false);
    }
  }, [api, tab]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { orders, stats, loading, fetch };
}
