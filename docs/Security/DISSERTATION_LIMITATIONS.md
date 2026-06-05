Dissertation: Security Limitations and Trade-offs

HS256 was chosen for simplicity in the development environment; production deployment would require RS256 with per-hospital key pairs.

Token storage and XSS risk

The frontend currently stores access and refresh tokens in sessionStorage (cleared on tab close). While this reduces persistence compared to localStorage, sessionStorage remains accessible to any JavaScript in the page and therefore is vulnerable to token theft via XSS. For a security-focused deployment, move to server-set HttpOnly, SameSite cookies for access and refresh tokens (or use short-lived access tokens with refresh rotation stored in HttpOnly cookies). Mitigations include: deploying a strict Content Security Policy (CSP), input/output escaping and sanitization, CSP + SRI for third-party scripts, and implementing cookie-based auth with CSRF protections. This document records the known limitation and recommends the migration plan be implemented before final submission.

Risk-based adaptive authentication

Blanket MFA is often a poor fit for clinical workflows because shared workstations, time-sensitive care, and restricted mobile-device use can encourage unsafe workarounds. The adaptive-auth model in this project reduces that friction by mapping routine access to a lower assurance tier and escalating only when the risk is higher, such as a new device or cross-hospital access. In dissertation terms, the model maps cleanly to NIST AAL1 for trusted routine access and AAL2 for email-OTP verification, with step-up challenges reserved for sensitive actions. TOTP authenticator apps were removed for clinical staff because email OTP better matches hospital workstation use, while TOTP remains appropriate for administrative roles where personal-device use is more practical.
