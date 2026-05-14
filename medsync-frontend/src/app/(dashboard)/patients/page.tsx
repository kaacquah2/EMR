"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PatientsListPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/patients/search");
  }, [router]);
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <p className="text-slate-500 dark:text-slate-500">Redirecting to patient search...</p>
    </div>
  );
}
