/**
 * In-app runbook anchors on /superadmin/system-health.
 * Optional: set NEXT_PUBLIC_OPS_DOCS_BASE (e.g. internal wiki URL) to open external docs instead.
 */
const externalBase =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_OPS_DOCS_BASE
    ? process.env.NEXT_PUBLIC_OPS_DOCS_BASE.replace(/\/$/, "")
    : "";

export type HealthServiceKey =
  | "api"
  | "database"
  | "redis"
  | "ai_inference"
  | "kms"
  | "audit_chain"
  | "backup";

export function runbookHref(serviceKey: HealthServiceKey): string {
  if (externalBase) {
    return `${externalBase}/${serviceKey}`;
  }
  return `/superadmin/system-health#svc-${serviceKey}`;
}

export const DASHBOARD_HEALTH_ROWS: ReadonlyArray<{ label: string; key: HealthServiceKey }> = [
  { label: "Django API", key: "api" },
  { label: "PostgreSQL", key: "database" },
  { label: "Redis / Celery", key: "redis" },
  { label: "AI inference", key: "ai_inference" },
  { label: "KMS / Encryption", key: "kms" },
  { label: "Audit chain", key: "audit_chain" },
  { label: "Backup", key: "backup" },
];
