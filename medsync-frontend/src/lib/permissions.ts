export const ALERT_RESOLVE_ROLES = ["doctor", "nurse"] as const;

export function canResolveAlerts(role: string | null | undefined): boolean {
  if (!role) return false;
  return ALERT_RESOLVE_ROLES.includes(role as (typeof ALERT_RESOLVE_ROLES)[number]);
}
