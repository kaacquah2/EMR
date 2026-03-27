import { API_BASE } from "./api-base";

/**
 * Trigger CSV download from an API endpoint that returns text/csv.
 * Uses the provided access token for auth.
 */
export async function downloadCsv(
  endpoint: string,
  accessToken: string | null,
  filename: string
): Promise<void> {
  if (!accessToken) return;
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
