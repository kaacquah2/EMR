import * as Sentry from "@sentry/nextjs";

/** Clinical route segments that may carry PHI in request bodies / breadcrumbs. */
const PHI_ROUTE_SEGMENTS = [
  "/patients/",
  "/encounters/",
  "/lab/",
  "/prescriptions/",
  "/admissions/",
  "/vitals/",
  "/records/",
  "/fhir/",
];

function containsPhiRoute(url?: string): boolean {
  if (!url) return false;
  return PHI_ROUTE_SEGMENTS.some((seg) => url.includes(seg));
}

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN,
  // Use 10% sampling in production — 1.0 is too expensive and noisy
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  debug: false,

  // Session Replay — mask all on-screen text and block media to prevent PHI capture
  replaysOnErrorSampleRate: 0.5,
  replaysSessionSampleRate: 0.05,
  integrations: [
    Sentry.replayIntegration({
      // Mask all text content and block all media in replays
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],

  // PHI SAFETY: Scrub request bodies on all clinical API routes
  beforeSend(event: Sentry.ErrorEvent) {
    // PHI SAFETY: Scrub request bodies and cookies from all clinical API routes
    if (event.request?.url && containsPhiRoute(event.request.url)) {
      delete event.request.data;
      delete event.request.cookies;
    }
    return event;
  },
});
