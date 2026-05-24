"use client";

import React, { useEffect } from "react";
import { useParams } from "next/navigation";
import { usePatient } from "@/hooks/use-patients";
import { PatientContextBanner } from "@/components/layout/PatientContextBanner";
import { useApi } from "@/hooks/use-api";
import { useState } from "react";

interface Allergy {
  id: string;
  allergen: string;
  severity: string;
}

interface ClinicalAlert {
  id: string;
  severity: string;
  message: string;
}

export default function PatientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const id = params.id as string;
  const { patient, loading } = usePatient(id);
  const api = useApi();
  const [allergies, setAllergies] = useState<Allergy[]>([]);
  const [activeAlerts, setActiveAlerts] = useState<ClinicalAlert[]>([]);

  useEffect(() => {
    if (!id) return;

    const fetchData = async () => {
      try {
        const [allergiesRes, alertsRes] = await Promise.all([
          api.get<{ results: Allergy[] }>(`/patients/${id}/allergies`),
          api.get<{ results: ClinicalAlert[] }>(`/patients/${id}/alerts?status=active`),
        ]);
        setAllergies(allergiesRes.results || []);
        setActiveAlerts(alertsRes.results || []);
      } catch (error) {
        console.error("Failed to fetch patient context data:", error);
      }
    };

    fetchData();
  }, [id, api]);

  if (loading || !patient) {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-col min-h-screen">
      <PatientContextBanner
        patient={{
          id: patient.id || patient.patient_id,
          full_name: patient.full_name,
          age: patient.age || 0,
          gender: patient.gender,
          ghana_health_id: patient.ghana_health_id,
          blood_group: patient.blood_group,
          admission_status: patient.admission_status,
          ward_name: patient.ward_name,
          bed_code: patient.bed_code,
          photo_url: patient.photo_url,
        }}
        allergies={allergies}
        activeAlerts={activeAlerts}
      />
      <main className="flex-1 p-4 md:p-8">
        {children}
      </main>
    </div>
  );
}
