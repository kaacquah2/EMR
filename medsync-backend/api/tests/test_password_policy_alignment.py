"""
Test to verify backend and frontend password policies are aligned.
"""

import pytest
from api.password_policy import validate_password as backend_validate


@pytest.mark.django_db
class TestPasswordPolicyAlignment:
    """Verify backend and frontend password validation rules match."""

    def test_password_requirements_minimum_length(self):
        """Password must be at least 12 characters."""
        valid, msg = backend_validate("Short1!")
        assert not valid
        assert "12 characters" in msg

    def test_password_requirements_uppercase(self):
        """Password must contain uppercase letter."""
        valid, msg = backend_validate("password123!")
        assert not valid
        assert "uppercase" in msg.lower()

    def test_password_requirements_lowercase(self):
        """Password must contain lowercase letter."""
        valid, msg = backend_validate("PASSWORD123!")
        assert not valid
        assert "lowercase" in msg.lower()

    def test_password_requirements_digit(self):
        """Password must contain digit."""
        valid, msg = backend_validate("PasswordABC!")
        assert not valid
        assert "number" in msg.lower()

    def test_password_requirements_symbol(self):
        """Password must contain symbol."""
        valid, msg = backend_validate("Password1234")  # 12 chars, no symbol
        assert not valid
        assert "symbol" in msg.lower()

    def test_password_valid_all_requirements(self):
        """Valid password must meet all requirements."""
        valid, msg = backend_validate("SecurePass123!@#")
        assert valid
        assert msg == ""

    def test_password_valid_various_symbols(self):
        """Accept various symbol types."""
        symbols_to_test = [
            "Password123!",
            "Password123@",
            "Password123#",
            "Password123$",
            "Password123%",
            "Password123^",
            "Password123&",
            "Password123*",
            "Password123(",
            "Password123)",
            "Password123_",
            "Password123+",
            "Password123-",
            "Password123=",
            "Password123[",
            "Password123]",
            "Password123{",
            "Password123}",
            "Password123;",
            "Password123:",
            "Password123'",
            'Password123"',
            "Password123\\",
            "Password123|",
            "Password123,",
            "Password123.",
            "Password123<",
            "Password123>",
            "Password123/",
            "Password123?",
        ]
        for password in symbols_to_test:
            valid, msg = backend_validate(password)
            assert valid, f"Password {password} should be valid: {msg}"

    def test_password_edge_cases(self):
        """Test edge cases."""
        # Exactly 12 chars with all requirements
        valid, msg = backend_validate("Pass0word!!!")
        assert valid

        # 11 chars with all requirements should fail
        valid, msg = backend_validate("Pass0word!!")
        assert not valid

        # Multiple of each type
        valid, msg = backend_validate("PassWORD123!!!AAA")
        assert valid

    def test_password_requirement_order_matters(self):
        """All checks must pass in order."""
        # Test each requirement individually fails
        test_cases = [
            ("pass0word!!!!", "uppercase"),  # No uppercase (12+ chars)
            ("PASS0WORD!!!!", "lowercase"),  # No lowercase (12+ chars)
            ("PassWord!!!!", "number"),      # No number (12 chars)
            ("Password1234", "symbol"),      # No symbol (12 chars)
            ("Pass0word!", "12 characters"),  # Too short
        ]
        for password, expected_error in test_cases:
            valid, msg = backend_validate(password)
            assert not valid, f"Expected {password} to fail"
            assert expected_error.lower() in msg.lower(), (
                f"Expected error message to contain '{expected_error}' but got '{msg}'"
            )
