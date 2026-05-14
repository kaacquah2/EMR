"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const RECORD_TYPES = [
  { id: "diagnosis", label: "Diagnosis" },
  { id: "prescription", label: "Prescription" },
  { id: "lab_order", label: "Lab Order" },
  { id: "vitals", label: "Vitals" },
  { id: "allergy", label: "Allergy" },
  { id: "nursing_note", label: "Nursing Note" },
];

export default function AddRecordPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [selectedType, setSelectedType] = useState<string | null>(null);

  if (user?.role !== "doctor") {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to add records.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.back()}>
          Back
        </Button>
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
          Add Clinical Record
        </h1>
      </div>

      {!selectedType ? (
        <Card>
          <CardHeader>
            <CardTitle>Select record type</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {RECORD_TYPES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedType(t.id)}
                  className="rounded-xl border-2 border-slate-300 dark:border-slate-700 p-6 text-left font-medium transition-colors hover:border-[#0B8A96] hover:bg-[#F0FDFA]"
                >
                  {t.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Add {RECORD_TYPES.find((t) => t.id === selectedType)?.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-slate-500 dark:text-slate-500">
              Form for {selectedType} will be implemented when backend is ready.
            </p>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={() => setSelectedType(null)}
            >
              Back to type selection
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
