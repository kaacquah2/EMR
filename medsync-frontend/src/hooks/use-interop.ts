"use client";

import { useState, useCallback } from "react";
import { useApi } from "./use-api";
import type {
  GlobalPatient,
  FacilityPatient,
  Facility,
  Consent,
  Referral,
  BreakGlassLog,
  CrossFacilityRecordsResponse,
} from "@/lib/types";

export function useGlobalPatientSearch() {
  const api = useApi();
  const [results, setResults] = useState<(GlobalPatient & { facility_ids?: string[]; facility_names?: string[] })[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setResults([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ query: query.trim() });
        const data = await api.get<{ data: GlobalPatient[] }>(
          `/global-patients/search?${params}`
        );
        setResults(data.data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { results, loading, error, search };
}

type FacilitiesSource = "interop" | "superadmin_hospitals";

export function useFacilities(source: FacilitiesSource = "interop") {
  const api = useApi();
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (source === "superadmin_hospitals") {
        const data = await api.get<{
          data: Array<{
            hospital_id: string;
            name: string;
            region?: string;
            nhis_code?: string;
            is_active?: boolean;
          }>;
        }>("/superadmin/hospitals");
        const rows = data.data || [];
        setFacilities(
          rows.map((h) => ({
            facility_id: h.hospital_id,
            name: h.name,
            region: h.region || "",
            nhis_code: h.nhis_code || "",
            is_active: h.is_active,
          }))
        );
      } else {
        const data = await api.get<{ data: Facility[] }>("/facilities");
        setFacilities(data.data || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load facilities");
      setFacilities([]);
    } finally {
      setLoading(false);
    }
  }, [api, source]);

  return { facilities, loading, error, fetch };
}

export function useCreateFacility() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(
    async (body: { name: string; nhis_code: string; region?: string; address?: string; phone?: string; email?: string; head_of_facility?: string }) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.post<{ facility_id: string; name: string; region: string; nhis_code: string }>("/facilities", body);
        return data;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create facility");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { create, loading, error };
}

export function useUpdateFacility() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = useCallback(
    async (
      facilityId: string,
      body: Partial<{ name: string; region: string; nhis_code: string; address: string; phone: string; email: string; head_of_facility: string; is_active: boolean }>
    ) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.patch<{ facility_id: string; name: string; region: string; nhis_code: string; is_active: boolean }>(
          `/facilities/${facilityId}`,
          body
        );
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to update facility";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { update, loading, error };
}

export function useLinkFacilityPatient() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const link = useCallback(
    async (body: { global_patient_id: string; local_patient_id?: string; facility_id?: string }) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.post<FacilityPatient>("/facility-patients/link", body);
        return res;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Link failed");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { link, loading, error };
}

export function useReferrals() {
  const api = useApi();
  const [incoming, setIncoming] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchIncoming = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ data: Referral[] }>("/referrals/incoming");
      setIncoming(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load referrals");
      setIncoming([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  const create = useCallback(
    async (body: { global_patient_id: string; to_facility_id: string; reason: string }) => {
      setError(null);
      try {
        return await api.post<Referral>("/referrals", body);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Create referral failed");
        throw err;
      }
    },
    [api]
  );

  const updateStatus = useCallback(
    async (referralId: string, status: Referral["status"]) => {
      setError(null);
      try {
        return await api.patch<Referral>(`/referrals/${referralId}`, { status });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Update failed");
        throw err;
      }
    },
    [api]
  );

  return { incoming, loading, error, fetchIncoming, create, updateStatus };
}

export function useConsents() {
  const api = useApi();
  const [list, setList] = useState<Consent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchList = useCallback(
    async (globalPatientId: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<{ data: Consent[] }>(
          `/consents/list?global_patient_id=${encodeURIComponent(globalPatientId)}`
        );
        setList(data.data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load consents");
        setList([]);
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  const grant = useCallback(
    async (body: {
      global_patient_id: string;
      granted_to_facility_id: string;
      scope: Consent["scope"];
      expires_at?: string | null;
    }) => {
      setError(null);
      try {
        return await api.post<Consent>("/consents", body);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Grant consent failed");
        throw err;
      }
    },
    [api]
  );

  const revoke = useCallback(
    async (consentId: string) => {
      setError(null);
      try {
        const updated = await api.patch<Consent>(`/consents/${consentId}`, {});
        setList((prev) =>
          prev.map((c) => (c.consent_id === consentId ? { ...c, ...updated, is_active: false } : c))
        );
        return updated;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Revoke consent failed");
        throw err;
      }
    },
    [api]
  );

  return { list, loading, error, fetchList, grant, revoke };
}

export function useBreakGlass() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(
    async (body: { global_patient_id: string; reason: string }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<BreakGlassLog>("/break-glass", body);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Break-glass failed");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { create, loading, error };
}

export function useBreakGlassList() {
  const api = useApi();
  const [list, setList] = useState<BreakGlassLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchList = useCallback(
    async (globalPatientId: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<{ data: BreakGlassLog[] }>(
          `/break-glass/list?global_patient_id=${encodeURIComponent(globalPatientId)}`
        );
        setList(data.data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load break-glass history");
        setList([]);
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { list, loading, error, fetchList };
}

export function useCrossFacilityRecords() {
  const api = useApi();
  const [data, setData] = useState<CrossFacilityRecordsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(
    async (globalPatientId: string) => {
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const res = await api.get<CrossFacilityRecordsResponse>(
          `/cross-facility-records/${globalPatientId}`
        );
        setData(res);
        return res;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load records");
        setData(null);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { data, loading, error, fetch };
}
