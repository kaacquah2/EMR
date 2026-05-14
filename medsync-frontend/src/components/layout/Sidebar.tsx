"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useSidebar } from "@/lib/sidebar-context";
import { Badge } from "@/components/ui/badge";
import { getNavigation } from "@/lib/navigation";
import { useApi } from "@/hooks/use-api";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { useNurseSidebarBadges } from "@/hooks/use-nurse-sidebar-badges";
import { ShiftWidget } from "@/components/features/ShiftWidget";
import { Tooltip } from "@/components/ui/Tooltip";
import {
  LayoutDashboard,
  Users,
  Calendar,
  FileText,
  Activity,
  AlertTriangle,
  Building2,
  Shield,
  Brain,
  Bed,
  Pill,
  Beaker,
  ClipboardList,
  Search,
  UserCog,
  Heart,
  Stethoscope,
  LogOut,
  type LucideIcon,
} from "lucide-react";

import { roleAccentColours } from "@/components/ui/badge";

type NavRow = { href: string; label: string; badge?: React.ReactNode; tag?: React.ReactNode };

// Icon mapping for navigation items
const navIconMap: Record<string, LucideIcon> = {
  // Common
  "Dashboard": LayoutDashboard,
  "Patient Search": Search,
  "Patients": Users,
  "Appointments": Calendar,
  "Admissions": Bed,
  "Alerts": AlertTriangle,
  "Worklist": ClipboardList,
  
  // Doctor
  "My Encounters": FileText,
  "AI Suite": Brain,
  "Referrals": Activity,
  
  // Nurse
  "Ward Patients": Users,
  "Batch Vitals": Heart,
  "Pending Dispense": Pill,
  "Nursing Notes": FileText,
  
  // Lab Tech
  "Lab Orders": Beaker,
  "Pending Results": ClipboardList,
  
  // Receptionist
  "Register Patient": UserCog,
  "Check-in": Calendar,
  
  // Hospital Admin
  "Staff Management": Users,
  "RBAC Review": Shield,
  "Audit Logs": FileText,
  "Reports": ClipboardList,
  
  // Super Admin
  "Hospitals": Building2,
  "Cross-Facility Monitor": Activity,
  "User Management": Users,
  "Break-glass review": Shield,
  "Facilities": Building2,
  "System health": Heart,
  "AI integration": Brain,
};

// Get icon for a navigation label
function getNavIcon(label: string): LucideIcon {
  return navIconMap[label] || Stethoscope;
}

// NavItem component for consistent rendering
interface NavItemProps {
  href: string;
  label: string;
  isActive: boolean;
  collapsed: boolean;
  badge?: React.ReactNode;
  tag?: React.ReactNode;
  onClick?: () => void;
  icon: LucideIcon;
}

function NavItem({ href, label, isActive, collapsed, badge, tag, onClick, icon: Icon }: NavItemProps) {
  const linkContent = (
    <Link
      href={href}
      onClick={onClick}
      className={
        "group relative flex items-center rounded-lg transition-all duration-150 " +
        (collapsed 
          ? "justify-center px-2 py-2.5 " 
          : "gap-3 px-3 py-2.5 ") +
        (isActive
          ? (collapsed 
              ? "bg-[rgba(11,138,150,0.2)] text-white shadow-[inset_0_0_0_1px_rgba(14,175,190,0.15)]"
              : "border-l-[3px] border-[#0EAFBE] bg-[rgba(11,138,150,0.2)] text-white shadow-[inset_0_0_0_1px_rgba(14,175,190,0.15)]")
          : "text-white/92 hover:bg-slate-800/80 hover:text-white")
      }
    >
      <Icon className={collapsed ? "h-5 w-5" : "h-4 w-4 flex-shrink-0"} />
      {!collapsed && <span className="text-sm font-medium truncate">{label}</span>}
      {!collapsed && badge}
      {!collapsed && tag}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip content={label} side="right">
        {linkContent}
      </Tooltip>
    );
  }

  return linkContent;
}

const AI_NEW_TAG_KEY = "medsync_ai_integration_new_seen";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, viewAsHospitalId } = useAuth();
  const api = useApi();
  const { collapsed, setCollapsed } = useSidebar();
  const [breakGlassUnreviewed, setBreakGlassUnreviewed] = useState<number | null>(null);
  const [haAlertCount, setHaAlertCount] = useState<number | null>(null);
  const [haRbacOverdue, setHaRbacOverdue] = useState<number | null>(null);
  const [aiNewSeen, setAiNewSeen] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      return localStorage.getItem(AI_NEW_TAG_KEY) === "1";
    } catch {
      return true;
    }
  });

  // Fetch nurse sidebar badges
  const nurseBadges = useNurseSidebarBadges(user?.role === "nurse");

  const role = user?.role ?? "";
  const viewAsActive = role === "super_admin" && !!viewAsHospitalId;
  const nav = getNavigation(role, { viewAsActive });
  const roleLabel = role ? role.replace(/_/g, " ") : "";

  // UX-24: listen for hamburger button events from TopBar
  useEffect(() => {
    const handler = () => setCollapsed(false);
    document.addEventListener("sidebar:open", handler);
    return () => document.removeEventListener("sidebar:open", handler);
  }, [setCollapsed]);

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;

    const fetchCount = async () => {
      try {
        const res = await api.get<{ data: unknown[] }>("/superadmin/break-glass-list-global?reviewed=false");
        const rows = Array.isArray(res?.data) ? res.data : [];
        if (!cancelled) setBreakGlassUnreviewed(rows.length);
      } catch {
        if (!cancelled) setBreakGlassUnreviewed(null);
      }
    };

    void fetchCount();
    return () => {
      cancelled = true;
    };
  }, [api, role]);
  usePollWhenVisible(
    () => {
      if (role !== "super_admin") return;
      void api
        .get<{ data: unknown[] }>("/superadmin/break-glass-list-global?reviewed=false")
        .then((res) => {
          const rows = Array.isArray(res?.data) ? res.data : [];
          setBreakGlassUnreviewed(rows.length);
        })
        .catch(() => setBreakGlassUnreviewed(null));
    },
    60_000,
    role === "super_admin"
  );

  const fetchHaBadges = React.useCallback(() => {
    if (role !== "hospital_admin") return;
    void api
      .get<{ total_count?: number }>("/alerts?resolved=false&limit=1")
      .then((res) => {
        if (typeof res?.total_count === "number") setHaAlertCount(res.total_count);
      })
      .catch(() => setHaAlertCount(null));
    void api
      .get<{ data: Array<{ days_overdue: number }> }>("/admin/rbac-review")
      .then((res) => {
        const rows = Array.isArray(res?.data) ? res.data : [];
        setHaRbacOverdue(rows.filter((r) => r.days_overdue > 0).length);
      })
      .catch(() => setHaRbacOverdue(null));
  }, [api, role]);

  useEffect(() => {
    fetchHaBadges();
  }, [fetchHaBadges]);

  usePollWhenVisible(fetchHaBadges, 60_000, role === "hospital_admin");

  const hospitalAdminSections = useMemo(() => {
    if (role !== "hospital_admin") return null;
    const clinical = nav.filter((item) => !item.href.startsWith("/admin"));
    const administration = nav.filter((item) => item.href.startsWith("/admin"));
    return { clinical, administration };
  }, [nav, role]);

  const superAdminSections = useMemo(() => {
    if (role !== "super_admin") return null;

    const badge =
      breakGlassUnreviewed == null ? null : (
        <span className="ml-auto rounded-full bg-white/15 px-2 py-0.5 text-xs font-semibold text-white">
          {breakGlassUnreviewed}
        </span>
      );

    const aiTag = aiNewSeen ? null : (
      <span className="ml-auto rounded-full bg-[#0EAFBE] px-2 py-0.5 text-[10px] font-bold uppercase text-white">
        New
      </span>
    );

    const system: NavRow[] = [
      { href: "/superadmin", label: "Dashboard" },
      { href: "/superadmin/hospitals", label: "Hospitals" },
      { href: "/superadmin/cross-facility-activity-log", label: "Cross-Facility Monitor" },
      { href: "/superadmin/audit-logs", label: "Audit Logs" },
      { href: "/superadmin/user-management", label: "User Management" },
      { href: "/superadmin/break-glass-review", label: "Break-glass review", badge },
    ];

    const config: NavRow[] = [
      { href: "/superadmin/facilities", label: "Facilities" },
      { href: "/superadmin/system-health", label: "System health" },
      { href: "/superadmin/ai-integration", label: "AI integration", tag: aiTag },
    ];

    const clinical: NavRow[] = !viewAsActive
      ? []
      : [
          { href: "/patients/search", label: "Patient Search" },
          { href: "/appointments", label: "Appointments" },
          { href: "/admissions", label: "Admissions" },
          { href: "/alerts", label: "Alerts" },
        ];

    return { system, config, clinical };
  }, [aiNewSeen, breakGlassUnreviewed, role, viewAsActive]);

  const brandHref = role === "super_admin" ? "/superadmin" : "/dashboard";

  if (!user) return null;

  return (
    <>
      {/* Mobile overlay backdrop */}
      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-black/40 hidden"
          onClick={() => setCollapsed(true)}
          aria-hidden="true"
        />
      )}
      <aside
        className={
          "sidebar-bg fixed left-0 top-0 z-40 hidden md:flex h-screen flex-col transition-all duration-200 " +
          (collapsed
            ? "w-16 -translate-x-full lg:translate-x-0"
            : "w-[260px]")
        }
      >
        {/* Teal accent strip on right edge when collapsed */}
        {collapsed && <div className="absolute right-0 top-0 h-full w-0.5 bg-[var(--teal-500)]/50" aria-hidden="true" />}

      <div className={"flex h-14 items-center border-b border-[#1A3A5C] " + (collapsed ? "justify-center px-2" : "justify-between px-4")}>
        {!collapsed && (
          <Link href={brandHref} className="font-sora text-lg font-bold text-white hover:text-[#BAE6FD] transition-colors">
            MedSync
          </Link>
        )}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className={"rounded-lg p-1.5 text-white/90 hover:bg-[#1A3A5C] hover:text-white transition-colors " + (collapsed ? "mx-auto" : "")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg
            className={"h-5 w-5 transition-transform " + (collapsed ? "rotate-180" : "")}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {!collapsed && (
        <div className="mx-2 mt-3 rounded-lg border border-[#1A3A5C]/80 bg-[#0C1F3D]/60 px-3 py-2.5">
          <p className="text-xs font-medium uppercase tracking-wider text-white/85">
            {user.hospital_name ?? (user.role === "super_admin" && !user.hospital_id ? "All hospitals" : "Hospital")}
          </p>
          <Badge
            variant="default"
            className="mt-1.5 border-0"
            style={roleAccentColours[user.role] ? { backgroundColor: `${roleAccentColours[user.role]}33`, color: roleAccentColours[user.role] } : undefined}
          >
            {roleLabel}
          </Badge>
        </div>
      )}

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-4">
        {user.role === "super_admin" && superAdminSections ? (
          <div className="space-y-4">
            {!collapsed && (
              <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-white/60">
                System
              </div>
            )}
            <div className="space-y-0.5">
              {superAdminSections.system.map((row) => {
                const isActive = pathname === row.href || pathname.startsWith(row.href + "/");
                return (
                  <NavItem
                    key={row.href}
                    href={row.href}
                    label={row.label}
                    isActive={isActive}
                    collapsed={collapsed}
                    badge={row.badge}
                    icon={getNavIcon(row.label)}
                  />
                );
              })}
            </div>

            {!collapsed && (
              <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-white/60">
                Configuration
              </div>
            )}
            <div className="space-y-0.5">
              {superAdminSections.config.map((row) => {
                const isActive = pathname === row.href || pathname.startsWith(row.href + "/");
                return (
                  <NavItem
                    key={row.href}
                    href={row.href}
                    label={row.label}
                    isActive={isActive}
                    collapsed={collapsed}
                    tag={row.tag}
                    icon={getNavIcon(row.label)}
                    onClick={row.href === "/superadmin/ai-integration" ? () => {
                      try {
                        localStorage.setItem(AI_NEW_TAG_KEY, "1");
                        setAiNewSeen(true);
                      } catch {
                        //
                      }
                    } : undefined}
                  />
                );
              })}
            </div>

            {superAdminSections.clinical.length > 0 && (
              <>
                {!collapsed && (
                  <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-white/60">
                    Clinical (View-As)
                  </div>
                )}
                <div className="space-y-0.5">
                  {superAdminSections.clinical.map((row) => {
                    const isActive = pathname === row.href || pathname.startsWith(row.href + "/");
                    return (
                      <NavItem
                        key={row.href}
                        href={row.href}
                        label={row.label}
                        isActive={isActive}
                        collapsed={collapsed}
                        icon={getNavIcon(row.label)}
                      />
                    );
                  })}
                </div>
              </>
            )}
          </div>
        ) : user.role === "hospital_admin" && hospitalAdminSections ? (
          <div className="space-y-4">
            {!collapsed && (
              <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-white/60">
                Clinical
              </div>
            )}
            <div className="space-y-0.5">
              {hospitalAdminSections.clinical.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
                const alertBadge =
                  item.href === "/alerts" && haAlertCount != null && haAlertCount > 0 ? (
                    <span className="ml-auto rounded-full bg-[#EF9F27]/90 px-2 py-0.5 text-[11px] font-semibold text-[#0C1F3D]">
                      {haAlertCount}
                    </span>
                  ) : null;
                return (
                  <NavItem
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    isActive={isActive}
                    collapsed={collapsed}
                    badge={alertBadge}
                    icon={getNavIcon(item.label)}
                  />
                );
              })}
            </div>
            {!collapsed && (
              <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-white/60">
                Administration
              </div>
            )}
            <div className="space-y-0.5">
              {hospitalAdminSections.administration.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
                const rbacBadge =
                  item.href === "/admin/rbac-review" && haRbacOverdue != null && haRbacOverdue > 0 ? (
                    <span className="ml-auto rounded-full bg-[#E24B4A]/90 px-2 py-0.5 text-[11px] font-semibold text-white">
                      {haRbacOverdue}
                    </span>
                  ) : null;
                return (
                  <NavItem
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    isActive={isActive}
                    collapsed={collapsed}
                    badge={rbacBadge}
                    icon={getNavIcon(item.label)}
                  />
                );
              })}
            </div>
          </div>
        ) : (
          nav.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

            // Add badges for nurse-specific items
            let itemBadge: React.ReactNode = null;
            if (role === "nurse" && !collapsed) {
              if (item.href === "/patients/vitals/new" && nurseBadges.vitals_overdue_count > 0) {
                itemBadge = (
                  <span className="ml-auto rounded-full bg-[#E24B4A]/90 px-2 py-0.5 text-[11px] font-semibold text-white">
                    {nurseBadges.vitals_overdue_count}
                  </span>
                );
              } else if (item.href === "/worklist/dispense" && nurseBadges.pending_dispense_count > 0) {
                itemBadge = (
                  <span className="ml-auto rounded-full bg-[#EF9F27]/90 px-2 py-0.5 text-[11px] font-semibold text-[#0C1F3D]">
                    {nurseBadges.pending_dispense_count}
                  </span>
                );
              } else if (item.href === "/alerts" && nurseBadges.active_alerts_count > 0) {
                itemBadge = (
                  <span className="ml-auto rounded-full bg-[#E24B4A]/90 px-2 py-0.5 text-[11px] font-semibold text-white">
                    {nurseBadges.active_alerts_count}
                  </span>
                );
              }
            }

            return (
              <NavItem
                key={item.href}
                href={item.href}
                label={item.label}
                isActive={isActive}
                collapsed={collapsed}
                badge={itemBadge}
                icon={getNavIcon(item.label)}
              />
            );
          })
        )}
      </nav>

      {/* Shift widget for nurses */}
      {role === "nurse" && !collapsed && <ShiftWidget />}

      <div className={"border-t border-[#1A3A5C] border-t-[#0B8A96]/30 " + (collapsed ? "p-2" : "p-4")}>
        {!collapsed && (
          <div className="mb-2 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0EAFBE] text-sm font-semibold text-white">
              {user.full_name?.charAt(0) || "U"}
            </div>
            <span className="truncate text-sm text-white">{user.full_name}</span>
          </div>
        )}
        {collapsed && (
          <div className="mb-2 flex justify-center">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0EAFBE] text-sm font-semibold text-white" title={user.full_name}>
              {user.full_name?.charAt(0) || "U"}
            </div>
          </div>
        )}
        <div className="flex flex-col gap-1.5">

          {collapsed ? (
            <Tooltip content="Log out" side="right">
              <button
                type="button"
                onClick={() => void logout()}
                className="group relative flex items-center justify-center rounded-lg p-2 text-white/92 hover:bg-slate-800 hover:text-white transition-colors"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </Tooltip>
          ) : (
            <button
              type="button"
              onClick={() => void logout()}
              className="group relative flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-white/92 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </button>
          )}
        </div>
      </div>
    </aside>
    </>
  );
}
