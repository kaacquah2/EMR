"use client";

import { useCallback } from "react";
import { useApi } from "./use-api";
import { User } from "@/lib/types";

export function useNurses() {
  const api = useApi();

  const getNursesAtHospital = useCallback(
    async (hospitalId: string): Promise<User[]> => {
      try {
        const response = await api.get<User[]>(`/admin/nurses?hospital_id=${hospitalId}`);
        return Array.isArray(response) ? response : [];
      } catch (err) {
        console.error("Failed to fetch nurses:", err);
        return [];
      }
    },
    [api]
  );

  return { getNursesAtHospital };
}
