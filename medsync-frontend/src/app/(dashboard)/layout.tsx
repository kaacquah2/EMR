"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { BottomNav } from "@/components/layout/BottomNav";
import { ViewAsBanner } from "@/components/layout/ViewAsBanner";
import { NetworkStatusBanner } from "@/components/ui/NetworkStatusBanner";
import { GracePeriodBanner } from "@/components/ui/GracePeriodBanner";
import { CommandPalette } from "@/components/ui/CommandPalette";
import { useAuth } from "@/lib/auth-context";
import { useSidebar } from "@/lib/sidebar-context";
import { isPathnameAccessible } from "@/lib/navigation";
import { SidebarProvider } from "@/lib/sidebar-context";

function DashboardLayoutContent({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, user, hydrated, viewAsHospitalId } = useAuth();
  const { collapsed } = useSidebar();
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
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[var(--cream-bg)] to-[#EDF2F7] dark:from-[#0F172A] dark:to-[#1A2E47]">
        <div className="text-[var(--gray-500)]">Loading...</div>
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
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[var(--cream-bg)] to-[#EDF2F7] dark:from-[#0F172A] dark:to-[#1A2E47]">
        <div className="text-[var(--gray-500)]">Redirecting...</div>
      </div>
    );
  }

  return (
    <>
      <NetworkStatusBanner />
      <ViewAsBanner />
      <GracePeriodBanner />
      <div className="flex min-h-screen bg-[var(--cream-bg)]">
        <Sidebar />
        <div
          className={`flex flex-1 flex-col transition-all duration-200 ${
            collapsed ? "lg:pl-16" : "lg:pl-[260px]"
          }`}
        >
          <TopBar />
          <main className="dashboard-main flex-1 p-4 pb-20 md:p-6 lg:p-8 md:pb-6 lg:pb-8">{children}</main>
        </div>
      </div>
      <BottomNav />
      <CommandPalette />
    </>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <DashboardLayoutContent>{children}</DashboardLayoutContent>
    </SidebarProvider>
  );
}
