"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SuperAdminFacilitiesWrapper() {
  const router = useRouter();
  useEffect(() => {
    const q = typeof window !== "undefined" ? window.location.search : "";
    router.replace(q ? `/admin/facilities${q}` : "/admin/facilities");
  }, [router]);
  return null;
}

