import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN,
  tracesSampleRate: 1.0,
  debug: false,
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  // PHI SAFETY: Never send sensitive clinical data to Sentry
  beforeSend(event: Sentry.ErrorEvent) {
    if (event.request?.url?.includes("/patients/")) {
      delete event.request.data;
    }
    return event;
  },
});
