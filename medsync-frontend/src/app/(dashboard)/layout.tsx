"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useAuth } from "@/lib/auth-context";
import { isPathnameAccessible } from "@/lib/navigation";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, user, hydrated, viewAsHospitalId } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated && !user) {
      router.replace("/login");
      return;
    }
    if (
      user?.role &&
      pathname != null &&
      !isPathnameAccessible(user.role, pathname, {
        viewAsActive: user.role === "super_admin" && !!viewAsHospitalId,
      })
    ) {
      router.replace("/unauthorized");
    }
  }, [hydrated, isAuthenticated, user, pathname, router, viewAsHospitalId]);

  // Show loading until auth is ready: not hydrated, or no session, or have token but user not yet loaded (/auth/me in flight)
  if (!hydrated || (!isAuthenticated && !user) || (isAuthenticated && !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#F5F3EE] to-[#EDF2F7]">
        <div className="text-[#64748B]">Loading...</div>
      </div>
    );
  }

  if (
    pathname != null &&
    user?.role &&
    !isPathnameAccessible(user.role, pathname, {
      viewAsActive: user.role === "super_admin" && !!viewAsHospitalId,
    })
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#F5F3EE] to-[#EDF2F7]">
        <div className="text-[#64748B]">Redirecting...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#F5F3EE]">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-[260px]">
        <TopBar />
        <main className="dashboard-main flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
