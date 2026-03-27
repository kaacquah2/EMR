const apiUrl = process.env.NEXT_PUBLIC_API_URL;

// Validate API URL at build/initialization time
let resolved: string;
function localApiFallback(): string {
  if (typeof window === "undefined") return "http://localhost:8000/api/v1";
  const host = window.location.hostname;
  // If frontend is opened from another device via LAN IP, localhost points to that device,
  // so target the same host on backend port 8000.
  if (host && host !== "localhost" && host !== "127.0.0.1") {
    const proto = window.location.protocol === "https:" ? "https:" : "http:";
    return `${proto}//${host}:8000/api/v1`;
  }
  return "http://localhost:8000/api/v1";
}
function adaptApiForLan(baseUrl: string): string {
  if (typeof window === "undefined") return baseUrl;
  try {
    const api = new URL(baseUrl);
    const appHost = window.location.hostname;
    const apiHost = api.hostname;
    const apiIsLocal = apiHost === "localhost" || apiHost === "127.0.0.1";
    const appIsLocal = appHost === "localhost" || appHost === "127.0.0.1";
    // If app is opened over LAN/IP but API env points to localhost,
    // localhost resolves on the client device, not the dev machine.
    if (apiIsLocal && !appIsLocal) {
      api.protocol = window.location.protocol === "https:" ? "https:" : "http:";
      api.hostname = appHost;
      api.port = "8000";
      return api.toString().replace(/\/$/, "");
    }
  } catch {
    return baseUrl;
  }
  return baseUrl;
}
if (!apiUrl) {
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    throw new Error(
      "❌ CRITICAL: NEXT_PUBLIC_API_URL environment variable is required in production.\n" +
      "   Set NEXT_PUBLIC_API_URL=https://your-api-domain.com/api/v1"
    );
  }
  // Development: warn about using default
  if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
    console.warn(
      `⚠️  Using default API URL (development only): ${localApiFallback()}\n` +
      "   For production, set NEXT_PUBLIC_API_URL environment variable to HTTPS URL"
    );
  }
  resolved = localApiFallback();
} else {
  // Require HTTPS in production only for non-localhost (allow http://localhost for local/CI builds)
  if (process.env.NODE_ENV === "production" && !apiUrl.startsWith("https://")) {
    let isLocal = false;
    try {
      const u = new URL(apiUrl);
      isLocal = u.hostname === "localhost" || u.hostname === "127.0.0.1";
    } catch {
      // invalid URL
    }
    if (!isLocal) {
      throw new Error(
        `❌ CRITICAL: NEXT_PUBLIC_API_URL must use HTTPS in production.\n` +
        `   Got: ${apiUrl}\n` +
        `   Expected: https://...`
      );
    }
  }
  resolved = adaptApiForLan(apiUrl);
}

export const API_BASE = resolved;

/** WebSocket base URL (origin only, ws/wss) for real-time features e.g. alerts. */
export function getWebSocketBase(): string {
  try {
    const u = new URL(resolved);
    const protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${u.host}`;
  } catch {
    return typeof window !== "undefined" ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}` : "ws://localhost:8000";
  }
}
