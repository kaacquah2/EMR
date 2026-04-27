"""
Mid-session role change semantics.

JWT access tokens identify the user by ID only. On each authenticated request,
``JWTAuthentication`` loads ``User`` from the database. Therefore a role change
in the DB takes effect on the very next API call with the same access token;
claims embedded at login time are not used for authorization.
"""

import pyotp
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import Hospital, User

_DEV_TOTP_SECRET = "JBSWY3DPEHPK3PXP"

# TOTP for these tests; real accounts use email OTP unless email is in DEV_PERMISSION_BYPASS_EMAILS.
_ROLE_CHANGE_DEV_MFA_EMAILS = [
    "demote_doc@test.gh",
    "promote_recv@test.gh",
    "jwt_load@test.gh",
]


def _user_with_mfa(hospital, email, role, password):
    u = User.objects.create_user(
        email=email,
        password=password,
        role=role,
        full_name="Role Change Test",
        hospital=hospital,
        account_status="active",
    )
    u.is_mfa_enabled = True
    u.totp_secret = _DEV_TOTP_SECRET
    u.save()
    return u


def _login_access_token(client: APIClient, email: str, password: str) -> str:
    r = client.post(
        "/api/v1/auth/login",
        {"email": email, "password": password},
        format="json",
    )
    assert r.status_code == 200, r.content
    mfa_token = r.json()["mfa_token"]
    code = pyotp.TOTP(_DEV_TOTP_SECRET).now()
    r2 = client.post(
        "/api/v1/auth/mfa-verify",
        {"mfa_token": mfa_token, "code": code},
        format="json",
    )
    assert r2.status_code == 200, r2.content
    return r2.json()["access_token"]


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(
        name="RoleChange Hospital",
        region="Test",
        nhis_code="RC99",
    )


@pytest.mark.django_db
@override_settings(DEV_PERMISSION_BYPASS_EMAILS=_ROLE_CHANGE_DEV_MFA_EMAILS)
def test_role_demotion_same_jwt_loses_doctor_only_access(hospital):
    """
    After admin changes role from doctor to receptionist, the same access token
    must not allow doctor-only endpoints (view checks request.user.role from DB).
    """
    pwd = "DocRoleChange123!@#"
    u = _user_with_mfa(hospital, "demote_doc@test.gh", "doctor", pwd)
    client = APIClient()
    access = _login_access_token(client, u.email, pwd)

    User.objects.filter(pk=u.pk).update(role="receptionist")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    res = client.post(
        "/api/v1/records/diagnosis",
        {"patient_id": str(u.id), "icd10_code": "A00"},
        format="json",
    )
    assert res.status_code == 403


@pytest.mark.django_db
@override_settings(DEV_PERMISSION_BYPASS_EMAILS=_ROLE_CHANGE_DEV_MFA_EMAILS)
def test_role_promotion_same_jwt_gains_hospital_admin_access(hospital):
    """
    After role is updated from receptionist to hospital_admin, the same JWT
    allows admin list (user loaded from DB each request).
    """
    pwd = "RecvRoleChange123!@#"
    u = _user_with_mfa(hospital, "promote_recv@test.gh", "receptionist", pwd)

    client = APIClient()
    access = _login_access_token(client, u.email, pwd)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    res_before = client.get("/api/v1/admin/users")
    assert res_before.status_code == 403

    User.objects.filter(pk=u.pk).update(role="hospital_admin")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    res_after = client.get("/api/v1/admin/users")
    assert res_after.status_code in (200, 400)


@pytest.mark.django_db
@override_settings(DEV_PERMISSION_BYPASS_EMAILS=_ROLE_CHANGE_DEV_MFA_EMAILS)
def test_jwt_authentication_loads_user_from_database_each_request(hospital):
    """
    Documented behaviour: each request resolves request.user via DB lookup by
    token user_id (Simple JWT), not a cached role from token payload.
    """
    from rest_framework_simplejwt.tokens import AccessToken

    pwd = "JwtLoad123!@#"
    u = _user_with_mfa(hospital, "jwt_load@test.gh", "doctor", pwd)
    token = AccessToken.for_user(u)
    assert token["user_id"] == str(u.pk)

    User.objects.filter(pk=u.pk).update(role="nurse")

    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework.request import Request
    from django.test import RequestFactory

    factory = RequestFactory()
    django_req = factory.get(
        "/api/v1/auth/me",
        HTTP_AUTHORIZATION=f"Bearer {str(token)}",
    )
    drf_req = Request(django_req)
    auth = JWTAuthentication()
    user, _ = auth.authenticate(drf_req)
    assert user.role == "nurse"


