from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.server_settings import (
    clear_server_settings_cache,
    set_advanced_library_groups_enabled,
    set_server_description,
    set_server_name,
)
from library.groups.services import configure_public_group, ensure_user_public_membership

from .models import UserProfile
from .services import get_or_create_profile


User = get_user_model()


class SetupAlreadyComplete(Exception):
    pass


def has_active_owner() -> bool:
    return User.objects.filter(is_active=True, is_superuser=True).exists()


@transaction.atomic
def create_first_owner(
    *,
    username: str,
    password: str,
    email: str = "",
    first_name: str = "",
    last_name: str = "",
    server_name: str = "Second Pass Library",
    server_description: str = "",
    public_group_name: str = "Common Room",
    public_group_description: str = "Main Public Library Room for everyone",
    advanced_library_groups_enabled: bool = False,
) -> Any:
    # Lock existing owner rows where the database supports row-level locking,
    # then re-check inside the creation transaction.
    list(
        User.objects.select_for_update()
        .filter(is_active=True, is_superuser=True)
        .values_list("pk", flat=True)
    )
    if has_active_owner():
        raise SetupAlreadyComplete

    username = User.normalize_username((username or "").strip())
    email = (email or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    validate_password(password, user=user)
    user.set_password(password)

    user.full_clean()

    try:
        set_server_name(server_name)
        set_server_description(server_description)
        configure_public_group(
            name=public_group_name,
            description=public_group_description,
        )
        set_advanced_library_groups_enabled(advanced_library_groups_enabled)
        user.save()
    except IntegrityError as exc:
        clear_server_settings_cache()
        raise ValidationError(
            {"username": "A user with that username already exists."}
        ) from exc
    except Exception:
        clear_server_settings_cache()
        raise

    profile = get_or_create_profile(user=user)
    profile.role = UserProfile.ROLE_MANAGER
    profile.must_change_password = False
    profile.full_clean()
    profile.save(update_fields=["role", "must_change_password", "updated_at"])

    ensure_user_public_membership(user=user)
    return user
