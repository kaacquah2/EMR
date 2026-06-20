"""
Custom middleware for MedSync EMR.

Note: several placeholder middleware classes that existed here (SessionIdleTimeout,
ForcedPasswordChange, ViewAsHospital, BreakGlassExpiry, CSP, RateLimitHeader) have
been removed because they were no-ops — every method returned None or pass.  Their
comments documented where the *real* enforcement lived:

  - Session idle timeout     → JWT expiry enforced by SimpleJWT on each request;
                               15-min client-side inactivity timer in auth-context.tsx.
  - ForcedPasswordChange     → frontend redirects to /auth/change-password-on-login.
  - ViewAsHospital           → api/utils.py:get_effective_hospital().
  - BreakGlassExpiry         → api/utils.py:can_access_cross_facility().
  - CSP                      → headers set in settings.py (SECURE_CONTENT_TYPE_OPTIONS,
                               CSP_* settings fed to django-csp).
  - RateLimitHeader          → DRF throttle classes add headers via their response hooks.

The AnomalyDetectionMiddleware (the only class that does real work) is in the
``api.middleware.anomaly_detection`` submodule and is still registered in settings.py.
"""
