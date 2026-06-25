"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { hasRole } from "@/lib/permissions";
import type { Role } from "@/lib/permissions";

interface RequireRoleProps {
  /** Allowed roles — any match grants access. */
  roles: readonly Role[];
  /** Where to redirect on denial (default: /unauthorized). */
  redirectTo?: string;
  children: React.ReactNode;
}

/**
 * Client-side RBAC guard. Redirects to `redirectTo` if the authenticated
 * user's role is not in `roles`. Also renders null during redirect to avoid flash.
 *
 * Usage:
 *   <RequireRole roles={ALL_ADMIN_ROLES}>
 *     <MyAdminPage />
 *   </RequireRole>
 */
export function RequireRole({ roles, redirectTo = "/unauthorized", children }: RequireRoleProps) {
  const { user } = useAuth();
  const router = useRouter();

  const allowed = !user || hasRole(user.role, roles);

  useEffect(() => {
    if (user && !hasRole(user.role, roles)) {
      router.replace(redirectTo);
    }
  }, [user, roles, redirectTo, router]);

  if (!allowed) return null;

  return <>{children}</>;
}
