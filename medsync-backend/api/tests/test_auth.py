import hashlib
import re
import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient
from django.utils import timezone
from core.models import User, Hospital, MFASession, AuditLog
import secrets
import string


# Test password helper (same as test_utils.py)
_TEST_PASSWORD = None


def _get_test_password():
    """Get or generate a test password. Uses same value throughout test session."""
    global _TEST_PASSWORD
    if _TEST_PASSWORD is None:
        chars = string.ascii_letters + string.digits + "!@#$"
        _TEST_PASSWORD = ''.join(secrets.choice(chars) for _ in range(12))
    return _TEST_PASSWORD


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="Test Hospital", region="Greater Accra", nhis_code="TH001")


@pytest.mark.django_db
class TestLogin:
    def test_login_requires_email_and_password(self, api_client):
        res = api_client.post("/api/v1/auth/login", {}, format="json")
        assert res.status_code == 400
        assert "required" in (res.json() or {}).get("message", "").lower()

    def test_login_invalid_credentials_or_restriction_returns_4xx(self, api_client, hospital):
        test_password = _get_test_password()
        User.objects.create_user(
            email="u@test.com", password=test_password, role="doctor", full_name="Dr U", hospital=hospital
        )
        res = api_client.post(
            "/api/v1/auth/login",
            {"email": "u@test.com", "password": "WrongPassNeverCorrect123!"},
            format="json",
        )
        assert res.status_code in (401, 403)
        assert "message" in (res.json() or {})


@pytest.mark.django_db
class TestMFAUserRateLimiting:
    def _create_mfa_user(self, hospital):
        password = _get_test_password()
        user = User.objects.create_user(
            email="mfa@test.com",
            password=password,
            role="doctor",
            full_name="Dr MFA",
            hospital=hospital,
        )
        user.is_mfa_enabled = True
        # Static but valid-looking TOTP secret; we will deliberately send wrong codes
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.save()
        return user

    def _create_mfa_session(self, user, token_suffix: str):
        # Wrong OTP hash so code "000000" always fails (email-OTP path for non–dev-seed users).
        wrong_plain = "111111"
        return MFASession.objects.create(
            user=user,
            token=f"mfa-token-{token_suffix}",
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            ip_address="127.0.0.1",
            user_agent="pytest",
            email_otp_hash=hashlib.sha256(wrong_plain.encode()).hexdigest(),
        )

    def test_mfa_rate_limit_per_user(self, api_client, hospital):
        """
        After enough failed MFA attempts across sessions, the user is locked and further
        MFA verification attempts return HTTP 429.
        """
        user = self._create_mfa_user(hospital)

        # Generate multiple failed MFA attempts to populate AuditLog with MFA_FAILED entries.
        for i in range(10):
            session = self._create_mfa_session(user, str(i))
            res = api_client.post(
                "/api/v1/auth/mfa-verify",
                {"mfa_token": session.token, "code": "000000"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"127.0.0.{i}",
            )
            # Until the threshold is reached, responses should be 401 Invalid code.
            assert res.status_code in (401, 429)

        # One more attempt should now hit the user-level rate limit and lock the account.
        session = self._create_mfa_session(user, "limit")
        res = api_client.post(
            "/api/v1/auth/mfa-verify",
            {"mfa_token": session.token, "code": "000000"},
            format="json",
            HTTP_X_FORWARDED_FOR="127.0.0.250",
        )
        assert res.status_code == 429
        body = res.json() or {}
        assert "account locked" in body.get("message", "").lower()

        user.refresh_from_db()
        assert user.locked_until is not None
        assert user.locked_until > timezone.now()

        # Verify that MFA_FAILED events were recorded for this user.
        failure_count = AuditLog.objects.filter(user=user, action="MFA_FAILED").count()
        assert failure_count >= 10

    def test_cannot_bruteforce_across_sessions(self, api_client, hospital):
        """
        Even when creating fresh MFA sessions, accumulated failures across sessions
        eventually lock the user and block further attempts.
        """
        user = self._create_mfa_user(hospital)

        # Use several distinct sessions with a couple of failures each to simulate
        # attempts spread across sessions.
        for i in range(5):
            session = self._create_mfa_session(user, f"multi-{i}")
            for _ in range(2):
                res = api_client.post(
                    "/api/v1/auth/mfa-verify",
                    {"mfa_token": session.token, "code": "000000"},
                    format="json",
                    HTTP_X_FORWARDED_FOR=f"127.0.1.{i}",
                )
                assert res.status_code in (401, 429)

        # One more attempt on a fresh session should now trigger the user-level lock.
        extra_session = self._create_mfa_session(user, "extra")
        res = api_client.post(
            "/api/v1/auth/mfa-verify",
            {"mfa_token": extra_session.token, "code": "000000"},
            format="json",
            HTTP_X_FORWARDED_FOR="127.0.2.1",
        )
        assert res.status_code == 429

        user.refresh_from_db()
        assert user.locked_until is not None
        assert user.locked_until > timezone.now()


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEV_PERMISSION_BYPASS_EMAILS=[],
)
def test_login_email_mfa_channel_and_verify(api_client, hospital):
    pwd = _get_test_password()
    user = User.objects.create_user(
        email="emailmfa@test.com",
        password=pwd,
        role="doctor",
        full_name="Email MFA",
        hospital=hospital,
    )
    user.is_mfa_enabled = True
    user.totp_secret = "JBSWY3DPEHPK3PXP"
    user.save()
    mail.outbox.clear()

    r1 = api_client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": pwd},
        format="json",
    )
    assert r1.status_code == 200
    body = r1.json()
    assert body.get("mfa_channel") == "email"
    assert body.get("mfa_token")
    assert len(mail.outbox) == 1
    m = re.search(r"code is:\s*(\d{6})", mail.outbox[0].body)
    assert m, mail.outbox[0].body
    otp = m.group(1)

    r2 = api_client.post(
        "/api/v1/auth/mfa-verify",
        {"mfa_token": body["mfa_token"], "code": otp},
        format="json",
    )
    assert r2.status_code == 200
    assert r2.json().get("access_token")


@pytest.mark.django_db
@override_settings(DEV_PERMISSION_BYPASS_EMAILS=["totpdev@test.com"])
def test_login_dev_seed_uses_authenticator_channel_not_email(api_client, hospital):
    import pyotp

    pwd = _get_test_password()
    secret = "JBSWY3DPEHPK3PXP"
    user = User.objects.create_user(
        email="totpdev@test.com",
        password=pwd,
        role="doctor",
        full_name="Dev TOTP",
        hospital=hospital,
    )
    user.is_mfa_enabled = True
    user.totp_secret = secret
    user.save()
    mail.outbox.clear()

    r1 = api_client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": pwd},
        format="json",
    )
    assert r1.status_code == 200
    body = r1.json()
    assert body.get("mfa_channel") == "authenticator"
    assert len(mail.outbox) == 0

    code = pyotp.TOTP(secret).now()
    r2 = api_client.post(
        "/api/v1/auth/mfa-verify",
        {"mfa_token": body["mfa_token"], "code": code},
        format="json",
    )
    assert r2.status_code == 200


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEV_PERMISSION_BYPASS_EMAILS=[],
)
def test_login_non_dev_user_with_totp_secret_uses_email_otp(api_client, hospital):
    """
    Verify that non-dev users with TOTP still use email OTP channel during login.
    This confirms that the system distinguishes between dev (TOTP only) and
    regular users (email OTP), while both can verify with TOTP if email fails.
    """
    import pyotp

    pwd = _get_test_password()
    secret = "JBSWY3DPEHPK3PXP"
    
    # Create a regular (non-dev) user with TOTP enabled
    user = User.objects.create_user(
        email="regular@test.com",  # NOT in DEV_PERMISSION_BYPASS_EMAILS
        password=pwd,
        role="doctor",
        full_name="Regular TOTP User",
        hospital=hospital,
    )
    user.is_mfa_enabled = True
    user.totp_secret = secret
    user.save()
    mail.outbox.clear()

    # Step 1: Login with email and password
    r1 = api_client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": pwd},
        format="json",
    )
    assert r1.status_code == 200
    body = r1.json()
    assert body.get("mfa_token")
    assert body.get("mfa_channel") == "email"  # Non-dev users get email OTP channel
    assert len(mail.outbox) == 1  # Email OTP was sent

    # Step 2: Verify with the email OTP code
    m = re.search(r"code is:\s*(\d{6})", mail.outbox[0].body)
    assert m, mail.outbox[0].body
    otp = m.group(1)
    
    r2 = api_client.post(
        "/api/v1/auth/mfa-verify",
        {"mfa_token": body["mfa_token"], "code": otp},
        format="json",
    )
    assert r2.status_code == 200
    assert r2.json().get("access_token")


@pytest.mark.django_db
class TestHealth:
    def test_health_returns_200_when_db_ok(self, api_client):
        res = api_client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json().get("status") == "ok"
        assert res.json().get("database") == "ok"


