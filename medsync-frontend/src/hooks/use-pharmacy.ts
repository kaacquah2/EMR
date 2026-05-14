"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import { useAuth } from "@/lib/auth-context";
import { useHospitalWS } from "./use-hospital-ws";

// ============================================================================
// TYPES
// ============================================================================

export interface DrugStock {
  id: string;
  hospital: string;
  hospital_name: string;
  drug_name: string;
  generic_name: string;
  batch_number: string;
  quantity: number;
  unit: string;
  reorder_level: number;
  expiry_date: string;
  supplier?: string;
  cost_per_unit?: number;
  stored_location?: string;
  notes?: string;
  is_low_stock: boolean;
  is_expired: boolean;
  days_until_expiry: number;
  created_at: string;
  updated_at: string;
}

export interface DrugStockDetail extends DrugStock {
  dispensations?: Dispensation[];
  movements?: StockMovement[];
}

export interface Dispensation {
  id: string;
  prescription_id: string;
  drug_stock: string;
  drug_stock_name: string;
  quantity_dispensed: number;
  dispensed_by: string;
  dispensed_by_name: string;
  dispensed_at: string;
  batch_notes?: string;
}

export interface StockMovement {
  id: string;
  drug_stock: string;
  drug_stock_name: string;
  movement_type: string;
  movement_type_display: string;
  quantity: number;
  quantity_before: number;
  quantity_after: number;
  reason: string;
  performed_by: string;
  performed_by_name?: string;
  dispensation?: string;
  created_at: string;
}

export interface StockAlert {
  id: string;
  hospital: string;
  hospital_name: string;
  drug_stock: string;
  drug_stock_name: string;
  drug_batch: string;
  alert_type: string;
  alert_type_display: string;
  message: string;
  severity: "critical" | "warning" | "info";
  severity_display: string;
  status: "active" | "acknowledged" | "resolved";
  status_display: string;
  acknowledged_by?: string;
  acknowledged_by_name?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface StockListResponse {
  count: number;
  results: DrugStock[];
}

export interface DispensationListResponse {
  count: number;
  results: Dispensation[];
}

export interface LowStockReportResponse {
  count: number;
  results: Array<{
    id: string;
    drug_name: string;
    batch_number: string;
    current_quantity: number;
    reorder_level: number;
    unit: string;
    shortage: number;
    expiry_date: string;
  }>;
}

export interface ExpiringStockReportResponse {
  count: number;
  results: Array<{
    id: string;
    drug_name: string;
    batch_number: string;
    quantity: number;
    unit: string;
    expiry_date: string;
    days_to_expiry: number;
    is_critical: boolean;
  }>;
}

// ============================================================================
// HOOK: DRUG STOCK MANAGEMENT
// ============================================================================

export function useDrugStock() {
  const api = useApi();
  const { user } = useAuth();
  const [stock, setStock] = useState<DrugStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getStock = useCallback(
    async (filters?: { drug_name?: string; low_stock?: boolean }) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (filters?.drug_name) params.append("drug_name", filters.drug_name);
        if (filters?.low_stock) params.append("low_stock", "true");

        const response = await api.get<{ data: StockListResponse }>(
          `/pharmacy/stock/?${params.toString()}`
        );
        const data = response.data;
        setStock(data.results || []);
        return data.results || [];
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load drug stock";
        setError(message);
        setStock([]);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const addStock = useCallback(
    async (stockData: {
      drug_name: string;
      generic_name?: string;
      batch_number: string;
      quantity: number;
      unit: string;
      reorder_level: number;
      expiry_date: string;
      supplier?: string;
      cost_per_unit?: number;
      stored_location?: string;
      notes?: string;
    }) => {
      setError(null);
      try {
        const response = await api.post<{ data: DrugStock }>("/pharmacy/stock/", stockData);
        const data = response.data;
        setStock((prev) => [data, ...prev]);
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to add stock";
        setError(message);
        throw err;
      }
    },
    [api]
  );

  const getStockDetail = useCallback(
    async (stockId: string) => {
      setError(null);
      try {
        const response = await api.get<{ data: DrugStockDetail }>(
          `/pharmacy/stock/${stockId}/`
        );
        return response.data;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load stock detail";
        setError(message);
        throw err;
      }
    },
    [api]
  );

  const adjustStock = useCallback(
    async (
      stockId: string,
      adjustment: {
        quantity_change: number;
        reason: string;
        movement_type?: string;
      }
    ) => {
      setError(null);
      try {
        const data = await api.post(`/pharmacy/stock/${stockId}/adjust/`, adjustment);
        // Refresh stock list after adjustment
        await getStock();
        return data;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to adjust stock";
        setError(message);
        throw err;
      }
    },
    [api, getStock]
  );

  // Listen for real-time stock updates
  useHospitalWS(user?.hospital_id, (event) => {
    // Refresh stock list on any stock-related event
    if (event.type === "stock_alert" || event.type === "pharmacy_event" || event.type === "alert_event") {
      getStock();
    }
  });

  return {
    stock,
    loading,
    error,
    getStock,
    addStock,
    getStockDetail,
    adjustStock,
  };
}

// ============================================================================
// HOOK: DISPENSATIONS
// ============================================================================

export function useDispensations() {
  const api = useApi();
  const [dispensations, setDispensations] = useState<Dispensation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getDispensations = useCallback(
    async (filters?: { patient_id?: string; drug_name?: string }) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (filters?.patient_id) params.append("patient_id", filters.patient_id);
        if (filters?.drug_name) params.append("drug_name", filters.drug_name);

        const response = await api.get<{ data: DispensationListResponse }>(
          `/pharmacy/dispensations/?${params.toString()}`
        );
        const data = response.data;
        setDispensations(data.results || []);
        return data.results || [];
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load dispensations";
        setError(message);
        setDispensations([]);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return {
    dispensations,
    loading,
    error,
    getDispensations,
  };
}

// ============================================================================
// HOOK: REPORTS
// ============================================================================

export function usePharmacyReports() {
  const api = useApi();
  const { user } = useAuth();
  const [lowStockItems, setLowStockItems] = useState<
    LowStockReportResponse["results"]
  >([]);
  const [expiringItems, setExpiringItems] = useState<
    ExpiringStockReportResponse["results"]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getLowStockReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<{ data: LowStockReportResponse }>(
        "/pharmacy/reports/low-stock/"
      );
      const data = response.data;
      setLowStockItems(data.results || []);
      return data.results || [];
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load low-stock report";
      setError(message);
      setLowStockItems([]);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [api]);

  const getExpiringReport = useCallback(
    async (days: number = 30) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get<{ data: ExpiringStockReportResponse }>(
          `/pharmacy/reports/expiring/?days=${days}`
        );
        const data = response.data;
        setExpiringItems(data.results || []);
        return data.results || [];
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load expiring report";
        setError(message);
        setExpiringItems([]);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const checkExpiryManually = useCallback(async () => {
    setError(null);
    try {
      const data = await api.post("/pharmacy/tasks/check-expiry/", {});
      return data;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to trigger expiry check";
      setError(message);
      throw err;
    }
  }, [api]);

  // Listen for real-time stock updates
  useHospitalWS(user?.hospital_id, (event) => {
    if (event.type === "stock_alert" || event.type === "pharmacy_event" || event.type === "alert_event") {
      getLowStockReport();
      getExpiringReport();
    }
  });

  return {
    lowStockItems,
    expiringItems,
    loading,
    error,
    getLowStockReport,
    getExpiringReport,
    checkExpiryManually,
  };
}

// ============================================================================
// HOOK: DISPENSING
// ============================================================================

export function usePharmacyDispensing() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dispenseConfirm = useCallback(
    async (
      prescriptionId: string,
      data: {
        drug_stock_id?: string;
        quantity?: number;
        notes?: string;
      }
    ) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.post(
          `/pharmacy/prescriptions/${prescriptionId}/dispense-confirm/`,
          data
        );
        return response;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to confirm dispensation";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return {
    loading,
    error,
    dispenseConfirm,
  };
}

// ============================================================================
// HOOK: PHARMACY WORKLIST
// ============================================================================

export interface PrescriptionItem {
  prescription_id: string;
  patient_id: string;
  patient_name: string;
  drug_name: string;
  dosage: string;
  frequency: string;
  duration_days: number | null;
  route: string;
  priority: "stat" | "urgent" | "routine";
  prescribed_by: string;
  prescribed_at: string;
  wait_time_minutes: number;
  allergy_conflict: boolean;
  drug_interaction_checked: boolean;
  drug_interactions: Array<{
    interacting_drug: string;
    severity: "mild" | "moderate" | "severe";
    description: string;
  }> | null;
  notes: string | null;
}

export interface WorklistData {
  worklist: PrescriptionItem[];
  summary: {
    total_pending: number;
    stat_count: number;
    urgent_count: number;
    routine_count: number;
  };
}

export function usePharmacyWorklist() {
  const api = useApi();
  const { user } = useAuth();
  const [data, setData] = useState<WorklistData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWorklist = useCallback(async () => {
    try {
      setError(null);
      const result = await api.get<WorklistData>("/pharmacy/worklist");
      setData(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load pharmacy worklist";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  // Initial fetch
  useEffect(() => {
    fetchWorklist();
  }, [fetchWorklist]);

  // Listen for real-time updates (new prescriptions or stock changes)
  useHospitalWS(user?.hospital_id, (event) => {
    // Refresh worklist on relevant events
    if (
      event.type === "stock_alert" || 
      event.type === "pharmacy_event" || 
      event.type === "alert_event" ||
      event.type === "prescription_created" // Assuming this might be an event
    ) {
      fetchWorklist();
    }
  });

  return {
    data,
    loading,
    error,
    fetchWorklist,
  };
}
