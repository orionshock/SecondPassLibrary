from __future__ import annotations

import time
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connection, transaction

from core.models import ServerSetting
from core.server_configuration import (
    ServerConfigurationPatchError,
    update_owner_server_configuration,
)
from core.server_settings import (
    clear_server_settings_cache,
    set_advanced_library_groups_enabled,
)
from library.groups.memberships import ensure_user_public_membership

from .models import UserProfile
from .profiles import get_or_create_profile


User = get_user_model()
FIRST_OWNER_SETUP_GUARD_KEY = "_first_owner_setup_transaction_guard"
SQLITE_SETUP_LOCK_RETRY_SECONDS = 10


class SetupAlreadyComplete(Exception):
    pass


def has_active_owner() -> bool:
    return User.objects.filter(is_active=True, is_superuser=True).exists()


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
    deadline = time.monotonic() + SQLITE_SETUP_LOCK_RETRY_SECONDS
    while True:
        try:
            return _create_first_owner_once(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                server_name=server_name,
                server_description=server_description,
                public_group_name=public_group_name,
                public_group_description=public_group_description,
                advanced_library_groups_enabled=advanced_library_groups_enabled,
            )
        except OperationalError as exc:
            # The atomic attempt has rolled back before control reaches here, but
            # cache reads performed inside it are not transactional.
            clear_server_settings_cache()
            if (
                connection.vendor != "sqlite"
                or "locked" not in str(exc).lower()
                or time.monotonic() >= deadline
            ):
                raise
            time.sleep(0.05)
        except Exception:
            clear_server_settings_cache()
            raise


@transaction.atomic
def _create_first_owner_once(
    *,
    username: str,
    password: str,
    email: str,
    first_name: str,
    last_name: str,
    server_name: str,
    server_description: str,
    public_group_name: str,
    public_group_description: str,
    advanced_library_groups_enabled: bool,
) -> Any:
    # This unique insert is the first database operation. It serializes setup
    # attempts even when there is no Owner row to lock. The row is deleted before
    # commit, so it is a transaction-scoped guard rather than persistent state.
    setup_guard = ServerSetting.objects.create(
        key=FIRST_OWNER_SETUP_GUARD_KEY,
        value=True,
        description="Transaction-scoped first Owner setup guard.",
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
        update_owner_server_configuration(
            patch={
                "server_name": server_name,
                "server_description": server_description,
                "public_group_name": public_group_name,
                "public_group_description": public_group_description,
            }
        )
        set_advanced_library_groups_enabled(advanced_library_groups_enabled)
        user.save()
    except IntegrityError as exc:
        raise ValidationError(
            {"username": "A user with that username already exists."}
        ) from exc
    except ServerConfigurationPatchError as exc:
        raise ValidationError(exc.errors) from exc

    profile = get_or_create_profile(user=user)
    profile.role = UserProfile.ROLE_MANAGER
    profile.must_change_password = False
    profile.full_clean()
    profile.save(update_fields=["role", "must_change_password", "updated_at"])

    ensure_user_public_membership(user=user)
    setup_guard.delete()
    return user
