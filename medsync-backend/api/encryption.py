"""
JWT Encryption/Decryption for HttpOnly Cookie Storage

Provides utilities for encrypting and decrypting JWT tokens before storage
in ClientCookie model. Uses Fernet symmetric encryption from cryptography library.

Rationale:
- JWTs in ClientCookie are encrypted at rest to prevent database breaches
- If database is compromised, encrypted JWTs are useless without the encryption key
- Encryption key should be stored separately (environment variable, key management service)
- Adds ~50ms per encryption/decryption operation (acceptable for authentication flows)
"""

import json
import logging
from functools import lru_cache
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_fernet_cipher():
    """
    Get or create Fernet cipher instance from Django settings.

    Reads ``settings.FIELD_ENCRYPTION_KEY`` — the same key used for field-level
    PHI encryption throughout the project.  Generate a new key with::

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    In DEBUG mode a fixed dev key is used so local development works without
    setting environment variables.  In production the app will not start if the
    key is missing or is the dev placeholder (caught by
    ``_assert_no_placeholder_secrets`` in settings.py).

    Raises:
        ImproperlyConfigured: In production when FIELD_ENCRYPTION_KEY is absent.
        ValueError: If the key value is not a valid Fernet key.
    """
    from django.conf import settings as _settings
    from django.core.exceptions import ImproperlyConfigured

    encryption_key = getattr(_settings, "FIELD_ENCRYPTION_KEY", None)

    if not encryption_key:
        if getattr(_settings, "DEBUG", False):
            # Dev-only fallback — safe because DEBUG=True prevents production
            # deployment and _assert_no_placeholder_secrets() blocks production
            # runs where FIELD_ENCRYPTION_KEY is absent.
            encryption_key = "dev-only-encryption-key-do-not-use-in-production"
            logger.warning(
                "JWT cookie encryption is using the dev placeholder key. "
                "Set FIELD_ENCRYPTION_KEY in production."
            )
        else:
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEY must be set in production for JWT cookie encryption."
            )

    try:
        # Fernet requires a URL-safe base64-encoded 32-byte key.  The dev
        # placeholder is not a valid Fernet key, so in DEBUG mode we derive one
        # deterministically rather than crashing on startup.
        if encryption_key == "dev-only-encryption-key-do-not-use-in-production":
            import base64, hashlib
            raw = hashlib.sha256(encryption_key.encode()).digest()
            encryption_key = base64.urlsafe_b64encode(raw).decode()

        return Fernet(
            encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
        )
    except Exception as e:
        logger.error(f"Failed to initialize Fernet cipher: {e}")
        raise ValueError(f"Invalid FIELD_ENCRYPTION_KEY: {e}")


def encrypt_jwt(jwt_token: str) -> str:
    """
    Encrypt a JWT token for storage in ClientCookie.
    
    Args:
        jwt_token: JWT string (e.g., access token from get_tokens_for_user)
    
    Returns:
        Encrypted token as string (safe to store in TextField)
    
    Raises:
        ValueError: If encryption fails
    """
    try:
        cipher = get_fernet_cipher()
        encrypted = cipher.encrypt(jwt_token.encode())
        return encrypted.decode()  # Store as string
    except Exception as e:
        logger.error(f"JWT encryption failed: {e}")
        raise ValueError(f"Failed to encrypt JWT: {e}")


def decrypt_jwt(encrypted_token: str) -> str:
    """
    Decrypt a JWT token from ClientCookie storage.
    
    Args:
        encrypted_token: Encrypted token string from ClientCookie.access_token_jwt
    
    Returns:
        Decrypted JWT token string
    
    Raises:
        ValueError: If decryption fails (token tampered, wrong key, expired)
    """
    try:
        cipher = get_fernet_cipher()
        decrypted = cipher.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except InvalidToken as e:
        logger.error(f"JWT decryption failed (invalid token): {e}")
        raise ValueError(f"Invalid or tampered JWT: {e}")
    except Exception as e:
        logger.error(f"JWT decryption failed: {e}")
        raise ValueError(f"Failed to decrypt JWT: {e}")


def encrypt_json(data: dict) -> str:
    """
    Encrypt a JSON-serializable dict for storage.
    
    Convenience method for encrypting structured data like client_metadata.
    
    Args:
        data: Dictionary to encrypt
    
    Returns:
        Encrypted JSON as string
    """
    try:
        json_str = json.dumps(data)
        return encrypt_jwt(json_str)  # Reuse JWT encryption
    except Exception as e:
        logger.error(f"JSON encryption failed: {e}")
        raise ValueError(f"Failed to encrypt JSON: {e}")


def decrypt_json(encrypted_data: str) -> dict:
    """
    Decrypt a JSON-encrypted dict from storage.
    
    Args:
        encrypted_data: Encrypted JSON string
    
    Returns:
        Decrypted dictionary
    """
    try:
        json_str = decrypt_jwt(encrypted_data)
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"JSON decryption failed: {e}")
        raise ValueError(f"Failed to decrypt JSON: {e}")
