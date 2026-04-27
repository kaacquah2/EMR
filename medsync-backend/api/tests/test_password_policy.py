import pytest
from api.password_policy import validate_password, check_password_reuse
from core.models import User, Hospital, UserPasswordHistory
from django.contrib.auth.hashers import make_password


@pytest.mark.django_db
class TestValidatePassword:
    def test_min_length(self):
        ok, msg = validate_password("Short1!")
        assert not ok
        assert "12" in msg

    def test_requires_uppercase(self):
        ok, msg = validate_password("alllowercase12!")
        assert not ok
        assert "uppercase" in msg.lower()

    def test_requires_lowercase(self):
        ok, msg = validate_password("ALLUPPERCASE12!")
        assert not ok
        assert "lowercase" in msg.lower()

    def test_requires_digit(self):
        ok, msg = validate_password("NoDigitsHere!")
        assert not ok
        assert "number" in msg.lower()

    def test_requires_symbol(self):
        ok, msg = validate_password("NoSymbolHere12")
        assert not ok
        assert "symbol" in msg.lower()

    def test_valid(self):
        ok, msg = validate_password("ValidPass12!")
        assert ok
        assert msg == ""


@pytest.mark.django_db
class TestCheckPasswordReuse:
    def test_no_history_allows_any(self):
        hospital = Hospital.objects.create(name="H", region="R", nhis_code="NH001")
        user = User.objects.create_user(
            email="u@test.com", password="FirstPass12!", role="doctor", full_name="Dr U", hospital=hospital
        )
        ok, msg = check_password_reuse(user, "NewPass12!")
        assert ok
        assert msg == ""

    def test_reuse_rejected(self):
        hospital = Hospital.objects.create(name="H", region="R", nhis_code="NH002")
        user = User.objects.create_user(
            email="u2@test.com", password="FirstPass12!", role="doctor", full_name="Dr U", hospital=hospital
        )
        UserPasswordHistory.objects.create(user=user, password_hash=make_password("OldPass12!"))
        ok, msg = check_password_reuse(user, "OldPass12!")
        assert not ok
        assert "reuse" in msg.lower() or "5" in msg

    def test_different_password_allowed(self):
        hospital = Hospital.objects.create(name="H", region="R", nhis_code="NH003")
        user = User.objects.create_user(
            email="u3@test.com", password="FirstPass12!", role="doctor", full_name="Dr U", hospital=hospital
        )
        UserPasswordHistory.objects.create(user=user, password_hash=make_password("OldPass12!"))
        ok, msg = check_password_reuse(user, "BrandNew12!")
        assert ok


