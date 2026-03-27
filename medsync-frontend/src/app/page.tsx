"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const hasSession = document.cookie.includes("medsync_session");
    if (!hasSession) {
      router.replace("/login");
      return;
    }
    try {
      const raw = sessionStorage.getItem("medsync_auth");
      const data = raw ? (JSON.parse(raw) as { user_profile?: { role?: string } }) : null;
      const role = data?.user_profile?.role;
      router.replace(role === "super_admin" ? "/superadmin" : "/dashboard");
    } catch {
      router.replace("/dashboard");
    }
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F5F3EE]">
      <p className="text-[#64748B]">Redirecting...</p>
    </div>
  );
}
