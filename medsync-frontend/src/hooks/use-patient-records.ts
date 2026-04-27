"use client";

import { useState, useCallback } from "react";
import { useApi } from "./use-api";
import type {
  MedicalRecord,
  Diagnosis,
  Prescription,
  LabResult,
  Vital,
} from "@/lib/types";

export function usePatientRecords(patientId: string | null) {
  const api = useApi();
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [labs, setLabs] = useState<LabResult[]>([]);
  const [vitals, setVitals] = useState<Vital[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecords = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ data: MedicalRecord[] }>(
        `/patients/${patientId}/records`
      );
      setRecords(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load records");
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [api, patientId]);

  const fetchDiagnoses = useCallback(async () => {
    if (!patientId) return;
    try {
      const data = await api.get<{ data: Diagnosis[] }>(
        `/patients/${patientId}/diagnoses`
      );
      setDiagnoses(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load diagnoses");
      setDiagnoses([]);
    }
  }, [api, patientId]);

  const fetchPrescriptions = useCallback(async () => {
    if (!patientId) return;
    try {
      const data = await api.get<{ data: Prescription[] }>(
        `/patients/${patientId}/prescriptions`
      );
      setPrescriptions(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load prescriptions");
      setPrescriptions([]);
    }
  }, [api, patientId]);

  const fetchLabs = useCallback(async () => {
    if (!patientId) return;
    try {
      const data = await api.get<{ data: LabResult[] }>(
        `/patients/${patientId}/labs`
      );
      setLabs(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load labs");
      setLabs([]);
    }
  }, [api, patientId]);

  const fetchVitals = useCallback(async () => {
    if (!patientId) return;
    try {
      const data = await api.get<{ data: Vital[] }>(
        `/patients/${patientId}/vitals`
      );
      setVitals(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load vitals");
      setVitals([]);
    }
  }, [api, patientId]);

  const fetchAll = useCallback(async (silent = false) => {
    if (!patientId) return;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [recRes, diagRes, rxRes, labRes, vitRes] = await Promise.all([
        api.get<{ data: MedicalRecord[] }>(`/patients/${patientId}/records`),
        api.get<{ data: Diagnosis[] }>(`/patients/${patientId}/diagnoses`),
        api.get<{ data: Prescription[] }>(`/patients/${patientId}/prescriptions`),
        api.get<{ data: LabResult[] }>(`/patients/${patientId}/labs`),
        api.get<{ data: Vital[] }>(`/patients/${patientId}/vitals`),
      ]);
      setRecords(recRes.data || []);
      setDiagnoses(diagRes.data || []);
      setPrescriptions(rxRes.data || []);
      setLabs(labRes.data || []);
      setVitals(vitRes.data || []);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : "Failed to load records");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [api, patientId]);

  return {
    records,
    diagnoses,
    prescriptions,
    labs,
    vitals,
    loading,
    error,
    fetchRecords,
    fetchDiagnoses,
    fetchPrescriptions,
    fetchLabs,
    fetchVitals,
    fetchAll,
  };
}
