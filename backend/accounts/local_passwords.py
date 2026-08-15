import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def user_supports_local_password(user) -> bool:
    if not user or getattr(user, "is_anonymous", False):
        return False
    has_usable_password = getattr(user, "has_usable_password", None)
    return bool(callable(has_usable_password) and has_usable_password())


def generate_temporary_password() -> str:
    # Short, URL-safe, cryptographically secure; shown once on create response only.
    return secrets.token_urlsafe(18)


def validate_new_password(*, new_password: str, user) -> None:
    new_password = (new_password or "").strip()
    if not new_password:
        raise ValidationError({"new_password": "New password is required."})

    validators = getattr(settings, "AUTH_PASSWORD_VALIDATORS", None) or []
    if validators:
        validate_password(new_password, user=user)
        return

    # Conventional fallback if validators are disabled.
    if len(new_password) < 8:
        raise ValidationError({"new_password": "New password must be at least 8 characters."})

