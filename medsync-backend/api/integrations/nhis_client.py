"""
Ghana NHIS Integration — API Client.

Implements:
  NHISClient            — synchronous HTTP client for Ghana NHIS API
  NHISEligibilityResult — typed result for eligibility checks
  NHISClaimResult       — typed result for claim submission/status
  NHISRetryableError    — transient error (network, rate-limit) → retry
  NHISClaimError        — permanent error (invalid data) → do not retry
  circuit_breaker       — prevents cascading failures when NHIS is down

API Base URL:
  The real Ghana NHIS API is operated by the National Health Insurance
  Authority (NHIA) and is only accessible to registered facilities.
  Endpoint structure is defined by NHIA's REST API specification (v2, 2024).

  Set the following in Django settings / environment:
    NHIS_API_BASE_URL      — base URL (e.g. https://api.nhia.gov.gh/v2)
    NHIS_API_KEY           — facility API key (from NHIA facility portal)
    NHIS_FACILITY_CODE     — NHIS facility code (== Hospital.nhis_code)
    NHIS_TIMEOUT_SECONDS   — request timeout (default: 10)
    NHIS_MAX_RETRIES       — max retry attempts (default: 3)
    NHIS_CIRCUIT_BREAKER_THRESHOLD — failures before circuit opens (default: 5)

Integration notes:
  - All calls are synchronous; for bulk processing wrap in a Celery task
  - NHIS API returns GHS currency (Ghana Cedi) amounts
  - Diagnosis codes must be ICD-10-CM formatted (e.g. "A09", "I10")
  - Claim reference numbers are NHIA-generated and must be stored
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from functools import wraps

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class NHISError(Exception):
    """Base NHIS error."""


class NHISRetryableError(NHISError):
    """Transient error — caller should retry (network timeout, 429, 503)."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class NHISClaimError(NHISError):
    """Permanent claim error — do NOT retry (invalid member, bad data, 400/422)."""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class NHISCircuitOpenError(NHISError):
    """Circuit breaker is open — NHIS API is unavailable. Do not call."""


# ============================================================================
# TYPED RESULT OBJECTS
# ============================================================================

@dataclass
class NHISEligibilityResult:
    """Result from NHIS member eligibility check."""
    is_eligible: bool
    member_id: str
    member_name: str
    card_status: str                     # "ACTIVE" | "EXPIRED" | "SUSPENDED" | "NOT_FOUND"
    card_expiry_date: Optional[datetime] = None
    benefit_package: Optional[str] = None   # e.g. "BASIC" | "PREMIUM"
    exemption_category: Optional[str] = None  # e.g. "PREGNANT" | "CHILD_UNDER_5" | "ELDERLY_70"
    facility_contracted: bool = True
    raw_response: Dict = field(default_factory=dict)

    @property
    def exemption_message(self) -> Optional[str]:
        if self.exemption_category == "PREGNANT":
            return "Patient is NHIS-exempt (pregnancy)"
        if self.exemption_category == "CHILD_UNDER_5":
            return "Patient is NHIS-exempt (child under 5)"
        if self.exemption_category == "ELDERLY_70":
            return "Patient is NHIS-exempt (age ≥ 70)"
        return None


@dataclass
class NHISClaimItem:
    """A single service item on an NHIS claim."""
    service_code: str      # NHIA service/tariff code
    description: str
    quantity: int = 1
    unit_price_ghs: Decimal = Decimal("0.00")
    nhis_tariff_ghs: Optional[Decimal] = None  # NHIA approved tariff (may differ from unit_price)


@dataclass
class NHISClaimResult:
    """Result from NHIS claim submission or status check."""
    claim_reference: str
    status: str            # "SUBMITTED" | "PROCESSING" | "APPROVED" | "REJECTED" | "QUERIED"
    submitted_at: Optional[datetime] = None
    approved_amount_ghs: Optional[Decimal] = None
    rejected_reason: Optional[str] = None
    queried_reason: Optional[str] = None
    raw_response: Dict = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        return self.status == "APPROVED"

    @property
    def is_rejected(self) -> bool:
        return self.status == "REJECTED"

    @property
    def requires_action(self) -> bool:
        return self.status == "QUERIED"


# ============================================================================
# SIMPLE CIRCUIT BREAKER
# ============================================================================

class _CircuitBreaker:
    """
    Basic circuit breaker to avoid hammering NHIS during outages.

    States:
      CLOSED  → normal operation (calls allowed)
      OPEN    → NHIS is down; reject calls immediately
      HALF_OPEN → test call allowed to check if NHIS recovered
    """

    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(self, threshold: int, recovery_seconds: int = 60):
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._state = self.STATE_CLOSED
        self._opened_at: Optional[datetime] = None

    @property
    def state(self) -> str:
        if self._state == self.STATE_OPEN:
            # Check if recovery window has passed
            if self._opened_at and (timezone.now() - self._opened_at).seconds > self.recovery_seconds:
                self._state = self.STATE_HALF_OPEN
                logger.info("NHIS circuit breaker: HALF-OPEN — testing recovery")
        return self._state

    def record_success(self):
        self._failure_count = 0
        if self._state == self.STATE_HALF_OPEN:
            logger.info("NHIS circuit breaker: CLOSED — API recovered")
        self._state = self.STATE_CLOSED

    def record_failure(self):
        self._failure_count += 1
        logger.warning(
            "NHIS circuit breaker: failure %d/%d", self._failure_count, self.threshold
        )
        if self._failure_count >= self.threshold:
            self._state = self.STATE_OPEN
            self._opened_at = timezone.now()
            logger.error(
                "NHIS circuit breaker: OPEN — NHIS API appears DOWN. "
                "Claims will use offline fallback for the next %d seconds.",
                self.recovery_seconds,
            )

    def allow_request(self) -> bool:
        return self.state in (self.STATE_CLOSED, self.STATE_HALF_OPEN)


# ============================================================================
# NHIS CLIENT
# ============================================================================

class NHISClient:
    """
    HTTP client for Ghana National Health Insurance Authority (NHIA) API.

    All methods raise:
      NHISRetryableError  — for transient failures (timeout, 429, 503)
      NHISClaimError      — for permanent failures (invalid data, 400, 422, 404)
      NHISCircuitOpenError — when circuit breaker is open

    Design:
      - Exponential backoff retry (3 attempts by default)
      - Circuit breaker (5 failures → open for 60 seconds)
      - All amounts returned in Ghana Cedi (GHS)
      - All API keys read from settings, never hardcoded
    """

    # Singleton circuit breaker shared across all instances
    _circuit_breaker: Optional[_CircuitBreaker] = None

    def __init__(self):
        self.base_url = getattr(settings, "NHIS_API_BASE_URL", "").rstrip("/")
        self.api_key = getattr(settings, "NHIS_API_KEY", "")
        self.facility_code = getattr(settings, "NHIS_FACILITY_CODE", "")
        self.timeout = getattr(settings, "NHIS_TIMEOUT_SECONDS", 10)
        self.max_retries = getattr(settings, "NHIS_MAX_RETRIES", 3)

        threshold = getattr(settings, "NHIS_CIRCUIT_BREAKER_THRESHOLD", 5)
        if NHISClient._circuit_breaker is None:
            NHISClient._circuit_breaker = _CircuitBreaker(threshold=threshold)

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "X-Facility-Code": self.facility_code,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _is_configured(self) -> bool:
        """True if API credentials are configured (production mode)."""
        return bool(self.base_url and self.api_key and self.facility_code)

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        """
        Execute an HTTP request with retry + circuit breaker.

        Returns parsed JSON response body.
        Raises NHISRetryableError or NHISClaimError on failure.
        """
        cb = NHISClient._circuit_breaker
        if not cb.allow_request():
            raise NHISCircuitOpenError(
                "NHIS API circuit breaker is OPEN — service appears unavailable. "
                "Claim will be queued for retry."
            )

        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.request(
                    method, url, timeout=self.timeout, **kwargs
                )

                if resp.status_code in (200, 201, 202):
                    cb.record_success()
                    return resp.json()

                # Rate limit — retryable
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 30))
                    cb.record_failure()
                    if attempt < self.max_retries:
                        logger.warning(
                            "NHIS rate limited (attempt %d/%d). Waiting %ds.",
                            attempt, self.max_retries, retry_after,
                        )
                        time.sleep(min(retry_after, 60))
                        continue
                    raise NHISRetryableError(
                        f"NHIS API rate limit exceeded after {self.max_retries} attempts",
                        status_code=429,
                    )

                # Server error — retryable
                if resp.status_code >= 500:
                    cb.record_failure()
                    if attempt < self.max_retries:
                        wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                        logger.warning(
                            "NHIS server error %d (attempt %d/%d). Waiting %ds.",
                            resp.status_code, attempt, self.max_retries, wait,
                        )
                        time.sleep(wait)
                        continue
                    raise NHISRetryableError(
                        f"NHIS API server error: {resp.status_code}",
                        status_code=resp.status_code,
                    )

                # Client error — not retryable
                if resp.status_code in (400, 404, 409, 422):
                    error_body = {}
                    try:
                        error_body = resp.json()
                    except Exception:
                        pass
                    error_msg = (
                        error_body.get("message")
                        or error_body.get("error")
                        or f"NHIS API error: HTTP {resp.status_code}"
                    )
                    error_code = error_body.get("error_code", str(resp.status_code))
                    raise NHISClaimError(
                        error_msg, error_code=error_code, status_code=resp.status_code
                    )

                # Unexpected status
                raise NHISRetryableError(
                    f"Unexpected NHIS response: {resp.status_code}",
                    status_code=resp.status_code,
                )

            except (requests.Timeout, requests.ConnectionError) as exc:
                cb.record_failure()
                last_exc = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "NHIS connection error (attempt %d/%d): %s. Waiting %ds.",
                        attempt, self.max_retries, exc, wait,
                    )
                    time.sleep(wait)
                    continue
                raise NHISRetryableError(
                    f"NHIS API unreachable after {self.max_retries} attempts: {exc}"
                ) from exc

            except (NHISRetryableError, NHISClaimError, NHISCircuitOpenError):
                raise

        raise NHISRetryableError(
            f"NHIS API failed after {self.max_retries} attempts",
        )

    # -------------------------------------------------------------------------
    # PUBLIC API METHODS
    # -------------------------------------------------------------------------

    def check_eligibility(self, nhis_member_id: str) -> NHISEligibilityResult:
        """
        Verify a patient's NHIS membership eligibility.

        Args:
            nhis_member_id: Patient's NHIS card number

        Returns:
            NHISEligibilityResult with card status, benefit package, exemptions

        NHIA API: GET /eligibility/{member_id}
        """
        if not self._is_configured():
            return self._mock_eligibility(nhis_member_id)

        logger.info("Checking NHIS eligibility for member: %s", nhis_member_id)
        data = self._request("GET", f"eligibility/{nhis_member_id}")

        card_status = data.get("card_status", "UNKNOWN")
        expiry_str = data.get("card_expiry_date")
        expiry_date = None
        if expiry_str:
            try:
                expiry_date = datetime.fromisoformat(expiry_str)
            except ValueError:
                pass

        return NHISEligibilityResult(
            is_eligible=card_status == "ACTIVE",
            member_id=nhis_member_id,
            member_name=data.get("member_name", ""),
            card_status=card_status,
            card_expiry_date=expiry_date,
            benefit_package=data.get("benefit_package"),
            exemption_category=data.get("exemption_category"),
            facility_contracted=data.get("facility_contracted", True),
            raw_response=data,
        )

    def submit_claim(
        self,
        invoice_id: str,
        nhis_member_id: str,
        diagnosis_codes: List[str],
        items: List[NHISClaimItem],
        visit_date: Optional[datetime] = None,
        attending_provider_id: Optional[str] = None,
    ) -> NHISClaimResult:
        """
        Submit a new claim to NHIS for processing.

        Args:
            invoice_id: Local invoice UUID (used as correlation ID)
            nhis_member_id: Patient's NHIS card number
            diagnosis_codes: List of ICD-10 codes (e.g. ["A09", "I10"])
            items: List of NHISClaimItem (services, drugs, labs)
            visit_date: Date of service (default: today)
            attending_provider_id: Provider NHIS registration number (optional)

        Returns:
            NHISClaimResult with NHIA-generated claim_reference

        NHIA API: POST /claims
        """
        if not self._is_configured():
            return self._mock_submit_claim(invoice_id, nhis_member_id, diagnosis_codes)

        payload = {
            "facility_code": self.facility_code,
            "member_id": nhis_member_id,
            "correlation_id": str(invoice_id),
            "visit_date": (visit_date or timezone.now()).date().isoformat(),
            "diagnosis_codes": diagnosis_codes,
            "attending_provider_id": attending_provider_id,
            "claim_items": [
                {
                    "service_code": item.service_code,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price_ghs),
                }
                for item in items
            ],
        }

        logger.info(
            "Submitting NHIS claim for invoice=%s member=%s items=%d",
            invoice_id, nhis_member_id, len(items),
        )
        data = self._request("POST", "claims", json=payload)

        return NHISClaimResult(
            claim_reference=data["claim_reference"],
            status=data.get("status", "SUBMITTED"),
            submitted_at=timezone.now(),
            raw_response=data,
        )

    def get_claim_status(self, claim_reference: str) -> NHISClaimResult:
        """
        Check the status of a submitted claim.

        NHIA API: GET /claims/{claim_reference}
        """
        if not self._is_configured():
            return self._mock_claim_status(claim_reference)

        logger.info("Checking NHIS claim status: %s", claim_reference)
        data = self._request("GET", f"claims/{claim_reference}")

        approved_amount = None
        if data.get("approved_amount"):
            try:
                approved_amount = Decimal(str(data["approved_amount"]))
            except Exception:
                pass

        return NHISClaimResult(
            claim_reference=claim_reference,
            status=data.get("status", "PROCESSING"),
            approved_amount_ghs=approved_amount,
            rejected_reason=data.get("rejected_reason"),
            queried_reason=data.get("queried_reason"),
            raw_response=data,
        )

    # -------------------------------------------------------------------------
    # OFFLINE / MOCK FALLBACK (when NHIS API is not configured)
    # -------------------------------------------------------------------------

    def _mock_eligibility(self, nhis_member_id: str) -> NHISEligibilityResult:
        """
        Offline fallback used in development / when NHIS_API_KEY is not set.
        Returns a plausible-looking but clearly mock result.
        """
        logger.warning(
            "NHIS API not configured (NHIS_API_KEY missing). "
            "Returning MOCK eligibility result for %s. "
            "Set NHIS_API_BASE_URL, NHIS_API_KEY, NHIS_FACILITY_CODE in settings for production.",
            nhis_member_id,
        )
        return NHISEligibilityResult(
            is_eligible=True,
            member_id=nhis_member_id,
            member_name="[OFFLINE MODE — Mock]",
            card_status="ACTIVE",
            card_expiry_date=datetime.now() + timedelta(days=365),
            benefit_package="BASIC",
            exemption_category=None,
            facility_contracted=True,
        )

    def _mock_submit_claim(
        self, invoice_id: str, nhis_member_id: str, diagnosis_codes: List[str]
    ) -> NHISClaimResult:
        """Offline fallback: simulate a successful claim submission."""
        from django.utils import timezone as tz
        now = tz.now()
        reference = f"NHIS-MOCK-{now.strftime('%Y%m%d')}-{str(invoice_id)[:8].upper()}"
        logger.warning(
            "NHIS API not configured. Returning MOCK claim reference: %s", reference
        )
        return NHISClaimResult(
            claim_reference=reference,
            status="SUBMITTED",
            submitted_at=now,
        )

    def _mock_claim_status(self, claim_reference: str) -> NHISClaimResult:
        """Offline fallback: simulate claim is being processed."""
        return NHISClaimResult(
            claim_reference=claim_reference,
            status="PROCESSING",
        )


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def get_nhis_client() -> NHISClient:
    """Factory function — returns a configured NHISClient instance."""
    return NHISClient()
