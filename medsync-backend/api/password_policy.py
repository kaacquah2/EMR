import re
from django.contrib.auth.hashers import check_password
from core.models import UserPasswordHistory

PASSWORD_HISTORY_COUNT = 5


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "Password must be at least 12 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain a number"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False, "Password must contain a symbol (!@#$%^&* etc.)"
    return True, ""


def check_password_reuse(user, new_password: str) -> tuple[bool, str]:
    """Return (True, '') if new_password is not in the last PASSWORD_HISTORY_COUNT hashes; else (False, message)."""
    history = list(
        UserPasswordHistory.objects.filter(user=user).order_by("-created_at")[:PASSWORD_HISTORY_COUNT].values_list(
            "password_hash", flat=True
        )
    )
    for old_hash in history:
        if check_password(new_password, old_hash):
            return False, "Cannot reuse any of your last 5 passwords."
    return True, ""


def record_password_history(user, current_hashed_password: str):
    """Append current hashed password to history and trim to PASSWORD_HISTORY_COUNT. Call before set_password(new)."""
    if not current_hashed_password or current_hashed_password.startswith("!"):
        return
    UserPasswordHistory.objects.create(user=user, password_hash=current_hashed_password)
    ids_to_keep = list(
        UserPasswordHistory.objects.filter(user=user).order_by("-created_at")[:PASSWORD_HISTORY_COUNT].values_list(
            "id", flat=True
        )
    )
    UserPasswordHistory.objects.filter(user=user).exclude(id__in=ids_to_keep).delete()
