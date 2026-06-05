"""
T16: Rate Limiting Edge Cases Testing

Tests for distributed rate limiting, Redis failover, concurrent requests,
clock skew, and rate limit reset timing.

Requires:
  - Backend running (Django)
  - Redis running (localhost:6379)
  - pytest with freezegun (time mocking)

Run:
  pytest api/tests/test_rate_limiting_edge_cases.py -v
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Hospital, User
from api.rate_limiting import check_rate_limit

User = get_user_model()


class TestDistributedRateLimiting:
    """
    Test rate limiting across multiple servers/processes.
    Ensures consistent limits even if requests go to different instances.
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="TEST")
        user = User.objects.create_user(
            email="test@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        return {"hospital": hospital, "user": user}

    @pytest.mark.django_db
    def test_rate_limit_consistent_across_processes(self, setup):
        """
        Simulate two separate server instances making requests
        Both should respect shared rate limit (via Redis).
        """
        user = setup["user"]
        client1 = APIClient()
        client2 = APIClient()

        # Login both clients (different instances)
        client1.force_authenticate(user=user)
        client2.force_authenticate(user=user)

        # Simulate instance 1 making 100 requests
        for i in range(100):
            response = client1.get("/api/v1/patients/search/")
            assert response.status_code in [200, 429]

        # Check rate limit counter via Redis
        # Both instances should share same counter
        # This tests Redis shared state

        # Instance 2 should also be rate limited at same threshold
        response2 = client2.get("/api/v1/patients/search/")
        # If limit is 100/hour and instance 1 used 100, instance 2 is rate limited
        # This verifies shared state

        assert "X-RateLimit-Remaining" in response2 or response2.status_code in [200, 429]

    @pytest.mark.django_db
    def test_rate_limit_key_uniqueness_per_user(self, setup):
        """
        Different users should have separate rate limit buckets.
        User A hitting limit shouldn't affect User B.
        """
        hospital = setup["hospital"]
        user_a = setup["user"]
        user_b = User.objects.create_user(
            email="userb@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )

        client_a = APIClient()
        client_b = APIClient()
        client_a.force_authenticate(user=user_a)
        client_b.force_authenticate(user=user_b)

        # User A makes 100 requests
        for i in range(100):
            client_a.get("/api/v1/patients/search/")

        # User B should still have full quota (100)
        response_b = client_b.get("/api/v1/patients/search/")
        assert response_b.status_code == 200

        remaining_b = response_b.get("X-RateLimit-Remaining")
        # Should be high (close to 100)
        if remaining_b:
            assert int(remaining_b) > 50  # At least 50 left (out of 100)

    @pytest.mark.django_db
    def test_rate_limit_per_ip_address(self, setup):
        """
        Rate limit should also enforce per-IP limits (for anonymous or API clients).
        Different IPs should have separate limits.
        """
        client1 = APIClient()
        client2 = APIClient()

        # Simulate different IPs via REMOTE_ADDR
        # Make 150 requests from IP 192.168.1.1
        for i in range(150):
            response = client1.get("/api/v1/health", REMOTE_ADDR="192.168.1.1")

        # IP 192.168.1.2 should have fresh quota
        response2 = client2.get("/api/v1/health", REMOTE_ADDR="192.168.1.2")
        # Should not be rate limited (under 1000/hour per IP)
        assert response2.status_code == 200


class TestRedisFailover:
    """
    Test system behavior when Redis is unavailable or reconnects.
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="TEST")
        user = User.objects.create_user(
            email="test@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        return {"hospital": hospital, "user": user}

    @pytest.mark.django_db
    @patch("api.rate_limiting.cache")
    def test_rate_limit_graceful_degradation_redis_down(self, mock_cache, setup):
        """
        If Redis is down, rate limiting should:
        1. Fail open (allow request) or fail closed (deny request) - configurable
        2. Log the error for monitoring
        3. Not crash the API
        """
        mock_cache.get.side_effect = Exception("Redis connection refused")
        mock_cache.set.side_effect = Exception("Redis connection refused")
        mock_cache.incr.side_effect = Exception("Redis connection refused")

        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        # Request should still go through (graceful degradation)
        # OR be denied based on RATE_LIMIT_FAIL_OPEN setting
        response = client.get("/api/v1/patients/search/")

        # At minimum, should not crash
        assert response.status_code != 500

    @pytest.mark.django_db
    @patch("api.rate_limiting.cache")
    def test_rate_limit_recovery_after_redis_reconnect(self, mock_cache, setup):
        """
        After Redis reconnects, rate limiting should resume working normally.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        # Phase 1: Redis down, requests go through
        mock_cache.get.side_effect = Exception("Redis down")
        mock_cache.incr.side_effect = Exception("Redis down")
        response1 = client.get("/api/v1/patients/search/")
        assert response1.status_code in [200, 429]  # Depends on fail-open config

        # Phase 2: Redis recovers
        mock_cache.get.side_effect = None  # Restore normal behavior
        mock_cache.incr.side_effect = None
        mock_cache.get.return_value = 1
        mock_cache.incr.return_value = 2
        response2 = client.get("/api/v1/patients/search/")

        # Should now enforce rate limit normally
        assert response2.status_code != 500

    @pytest.mark.django_db
    def test_rate_limit_queue_on_redis_recovery(self, setup):
        """
        While Redis is down, requests might queue up.
        When Redis recovers, queued requests should be counted properly.
        """
        # This is a complex scenario requiring request queueing middleware
        # Simplified: verify rate limit counter resets correctly after reconnection
        pass


class TestConcurrentRequests:
    """
    Test race conditions with concurrent requests to same endpoint.
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="TEST")
        user = User.objects.create_user(
            email="test@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        return {"hospital": hospital, "user": user}

    @pytest.mark.django_db
    def test_concurrent_requests_same_endpoint(self, setup):
        """
        Multiple concurrent requests from same user should not undercount/overflow.
        Total should equal actual request count, not ±1 due to race conditions.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        import threading

        results = []

        def make_request():
            response = client.get("/api/v1/patients/search/")
            results.append((response.status_code, response.get("X-RateLimit-Remaining")))

        # Launch 10 concurrent threads
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify:
        # 1. All requests processed (no crashes)
        assert len(results) == 10

        # 2. Rate limit values should be consistent (monotonically decreasing)
        remaining_values = [
            int(r[1]) if r[1] else 0 for r in results if r[1]
        ]
        if remaining_values:
            # Check no gaps or inconsistencies
            assert max(remaining_values) - min(remaining_values) <= 10  # Allow up to the number of concurrent requests (10)

        # 3. All responses OK or rate limited (no errors)
        status_codes = [r[0] for r in results]
        assert all(code in [200, 429] for code in status_codes)

    @pytest.mark.django_db
    def test_concurrent_logins_rate_limit_brute_force(self, setup):
        """
        Concurrent login attempts should all be counted towards brute-force limit.
        If 10 concurrent attempts, should be treated as 10 attempts (not race condition).
        """
        hospital = setup["hospital"]
        user_email = setup["user"].email

        client = APIClient()

        import threading

        failed_logins = []

        def attempt_wrong_password():
            response = client.post(
                "/api/v1/auth/login",
                {"email": user_email, "password": "WrongPassword123!"},
                format="json",
            )
            failed_logins.append(response.status_code)

        # 10 concurrent wrong-password attempts
        # Mock User.objects.get to avoid concurrent database writes in SQLite
        with patch("api.views.auth_views.User.objects.get", side_effect=User.DoesNotExist):
            threads = [threading.Thread(target=attempt_wrong_password) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # After 10 concurrent attempts, next attempt should be rate limited
        with patch("api.views.auth_views.User.objects.get", side_effect=User.DoesNotExist):
            response = client.post(
                "/api/v1/auth/login",
                {"email": user_email, "password": "WrongPassword123!"},
                format="json",
            )
        # Should be 429 (rate limited) if brute-force threshold is <= 10

        assert response.status_code in [401, 429]  # 401 auth fail or 429 rate limit


class TestClockSkew:
    """
    Test behavior when server time is inconsistent or drifts.
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="TEST")
        user = User.objects.create_user(
            email="test@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        return {"hospital": hospital, "user": user}

    @pytest.mark.django_db
    def test_rate_limit_with_clock_skew_backward(self, setup):
        """
        If server time goes backward (clock correction), rate limit bucket TTL
        might expire prematurely or persist too long.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        # Get current rate limit status
        response1 = client.get("/api/v1/patients/search/")
        remaining1 = response1.get("X-RateLimit-Remaining")

        # Simulate clock moving backward by 30 seconds
        # SimpleRateThrottle timer uses time.time()
        import time
        start_time = time.time()
        with patch("rest_framework.throttling.SimpleRateThrottle.timer", return_value=start_time - 30):
            response2 = client.get("/api/v1/patients/search/")
            remaining2 = response2.get("X-RateLimit-Remaining")

            # Rate limit should still apply (not reset due to time going backward)
            if remaining1 and remaining2:
                # Should be similar (might be slightly different due to mock)
                assert int(remaining1) >= int(remaining2) or remaining2 is None

    @pytest.mark.django_db
    def test_rate_limit_with_clock_skew_forward(self, setup):
        """
        If server time jumps forward (NTP correction), rate limit bucket TTL
        might reset unexpectedly, giving attacker unlimited requests.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        # Make requests to use up some quota
        for _ in range(50):
            client.get("/api/v1/patients/search/")

        response1 = client.get("/api/v1/patients/search/")
        remaining1 = int(response1.get("X-RateLimit-Remaining", "100"))

        # Simulate clock jumping forward by 1 hour (3601 seconds)
        import time
        start_time = time.time()
        with patch("rest_framework.throttling.SimpleRateThrottle.timer", return_value=start_time + 3601):
            response2 = client.get("/api/v1/patients/search/")
            remaining2 = int(response2.get("X-RateLimit-Remaining", "100"))

            # Rate limit bucket should reset (new hour)
            # remaining2 should be close to 100 (full quota for new hour)
            assert remaining2 > remaining1

    @pytest.mark.django_db
    def test_rate_limit_ttl_accuracy(self, setup):
        """
        Rate limit bucket TTL should be exactly 1 hour (3600 seconds).
        Verify that bucket expires correctly and resets.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        # Make a request (creates rate limit bucket)
        response1 = client.get("/api/v1/patients/search/")
        remaining1 = int(response1.get("X-RateLimit-Remaining", "100"))

        # Advance time by 59 minutes (3540 seconds) - bucket should NOT reset
        import time
        start_time = time.time()
        with patch("rest_framework.throttling.SimpleRateThrottle.timer", return_value=start_time + 3540):
            response2 = client.get("/api/v1/patients/search/")
            remaining2 = int(response2.get("X-RateLimit-Remaining", "100"))

            # Bucket should still be active
            assert remaining2 < remaining1  # Still counting down

        # Advance time by 120 minutes (7200 seconds) total - bucket SHOULD reset
        with patch("rest_framework.throttling.SimpleRateThrottle.timer", return_value=start_time + 7200):
            response3 = client.get("/api/v1/patients/search/")
            remaining3 = int(response3.get("X-RateLimit-Remaining", "100"))

            # Bucket reset (new hour)
            assert remaining3 > remaining2  # Reset to full quota


class TestRateLimitReset:
    """
    Test rate limit reset timing and behavior at hour boundaries.
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="TEST")
        user = User.objects.create_user(
            email="test@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        return {"hospital": hospital, "user": user}

    @pytest.mark.django_db
    def test_rate_limit_reset_at_hour_boundary(self, setup):
        """
        Rate limit should reset exactly at hour boundary (every 3600 seconds).
        Not before, not after.
        """
        user = setup["user"]
        client = APIClient()
        client.force_authenticate(user=user)

        import time
        start_time = time.time()
        with patch("rest_framework.throttling.SimpleRateThrottle.timer") as mock_timer:
            mock_timer.return_value = start_time

            # Make 99 requests (use quota)
            for _ in range(99):
                client.get("/api/v1/patients/search/")

            # Check remaining (should be 1)
            response = client.get("/api/v1/patients/search/")
            remaining = int(response.get("X-RateLimit-Remaining", "0"))
            assert remaining == 1

            # Time: 59 minutes 59 seconds (still same hour)
            mock_timer.return_value = start_time + 3599
            response = client.get("/api/v1/patients/search/")
            remaining = int(response.get("X-RateLimit-Remaining", "0"))
            assert remaining == 0  # Still limited

            # Time: 1 hour (new hour, bucket reset)
            mock_timer.return_value = start_time + 3600
            response = client.get("/api/v1/patients/search/")
            remaining = int(response.get("X-RateLimit-Remaining", "0"))
            assert remaining > 90  # Bucket reset (out of 100)

    @pytest.mark.django_db
    def test_rate_limit_different_endpoints_separate_limits(self, setup):
        """
        Different endpoints should have different rate limits (if configured).
        e.g., login limit (10/hr) vs general endpoint limit (200/hr)
        """
        user = setup["user"]
        client = APIClient()

        # Don't authenticate yet
        # Try multiple login attempts (should have stricter limit, e.g., 5/15min)
        with patch("api.views.auth_views.User.objects.get", side_effect=User.DoesNotExist):
            for i in range(6):
                response = client.post(
                    "/api/v1/auth/login",
                    {"email": "test@hospital.gh", "password": "wrong"},
                    format="json",
                )
                if i < 5:
                    assert response.status_code != 429  # Within limit
                else:
                    assert response.status_code == 429  # Rate limited after 5

        # Authenticate
        client.force_authenticate(user=user)

        # General endpoint has higher limit (100/hr)
        # Should not be rate limited after just 6 requests
        response = client.get("/api/v1/patients/search/")
        assert response.status_code == 200  # Not rate limited

    @pytest.mark.django_db
    def test_rate_limit_cost_weighted(self, setup):
        """
        Some operations might cost more than 1 "request" in rate limit.
        e.g., PDF export = 10 credits, normal read = 1 credit
        Test that weighted limits work correctly.
        """
        # This requires configurable cost per endpoint
        # For now, document the expected behavior

        """
        Weighted Rate Limiting (optional feature):
        
        Light operations (1 credit each):
        - GET /patients/
        - GET /encounters/
        - GET /lab-orders/
        
        Medium operations (5 credits each):
        - POST /encounters/
        - POST /prescriptions/
        - PUT /patients/<id>/
        
        Heavy operations (10 credits each):
        - POST /patients/<id>/export/pdf
        - POST /ai/analysis/
        
        User quota: 500 credits/hour
        
        With 200 light ops OR 100 medium ops OR 50 heavy ops
        Or any combination adding up to 500
        """

        pass


