"use client";

import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AddRecordForm } from "@/components/features/AddRecordForm";
import { Button } from "@/components/ui/button";
import { hasRole, RECORD_CREATE_ROLES } from "@/lib/permissions";

export default function AddRecordPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();
  const { user } = useAuth();

  if (!hasRole(user?.role, RECORD_CREATE_ROLES)) {
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
      <AddRecordForm
        patientId={id}
        onSuccess={() => router.push(`/patients/${id}`)}
        onClose={() => router.back()}
      />
    </div>
  );
}
