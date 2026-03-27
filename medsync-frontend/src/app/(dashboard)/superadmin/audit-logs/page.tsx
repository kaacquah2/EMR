"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SuperAdminAuditLogsWrapper() {
  const router = useRouter();
  useEffect(() => {
    const q = typeof window !== "undefined" ? window.location.search : "";
    router.replace(q ? `/admin/audit-logs${q}` : "/admin/audit-logs");
  }, [router]);
  return null;
}

