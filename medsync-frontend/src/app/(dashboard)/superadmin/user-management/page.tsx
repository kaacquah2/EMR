"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SuperAdminUserManagementWrapper() {
  const router = useRouter();
  useEffect(() => {
    const q = typeof window !== "undefined" ? window.location.search : "";
    router.replace(q ? `/admin/users${q}` : "/admin/users");
  }, [router]);
  return null;
}

