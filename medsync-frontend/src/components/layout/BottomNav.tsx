"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  AlertTriangle,
  FileText,
} from "lucide-react";

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  if (!user) return null;

  // Define nav items based on role
  let navItems = [
    { href: "/dashboard", label: "Home", icon: LayoutDashboard },
    { href: "/patients/search", label: "Patients", icon: Users },
  ];

  if (user.role === "doctor" || user.role === "nurse") {
    navItems.push(
      { href: "/worklist", label: "Worklist", icon: ClipboardList },
      { href: "/alerts", label: "Alerts", icon: AlertTriangle }
    );
  } else if (user.role === "super_admin") {
    navItems = [
      { href: "/superadmin", label: "System", icon: LayoutDashboard },
      { href: "/superadmin/hospitals", label: "Hospitals", icon: Users },
      { href: "/superadmin/audit-logs", label: "Logs", icon: FileText },
    ];
  } else if (user.role === "hospital_admin") {
    navItems.push(
      { href: "/admin/users", label: "Staff", icon: Users },
      { href: "/alerts", label: "Alerts", icon: AlertTriangle }
    );
  } else if (user.role === "receptionist") {
    navItems.push(
      { href: "/patients/register", label: "Register", icon: FileText },
      { href: "/appointments", label: "Schedule", icon: ClipboardList }
    );
  }

  // Cap at 4 or 5 items
  navItems = navItems.slice(0, 5);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-16 w-full border-t border-slate-200 bg-white pb-safe dark:border-slate-800 dark:bg-slate-900 md:hidden shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
      {navItems.map((item) => {
        const isActive =
          pathname === item.href ||
          (item.href !== "/dashboard" &&
            item.href !== "/superadmin" &&
            pathname?.startsWith(item.href));

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-1 flex-col items-center justify-center gap-1 px-2 py-1 transition-colors ${
              isActive
                ? "text-blue-600 dark:text-blue-400"
                : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
            }`}
          >
            <item.icon className={`h-5 w-5 ${isActive ? "fill-blue-100/50 dark:fill-blue-900/50" : ""}`} />
            <span className="text-[10px] font-medium">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
