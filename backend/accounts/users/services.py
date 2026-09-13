from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from accounts.local_passwords import generate_temporary_password
from accounts.models import UserProfile
from accounts.operational_logging import logger, user_log_label
from accounts.profiles import get_or_create_profile
from accounts.roles import RoleRank, effective_role_rank, is_manager, is_owner
from core.operational_logging import info_on_commit
from library.groups.memberships import ensure_user_public_membership


User = get_user_model()


@dataclass(frozen=True)
class UserUpdateResult:
    user: Any
    profile: UserProfile


@dataclass(frozen=True)
class ManagedUserCreateResult:
    user: Any
    temporary_password: str



def _is_exact_manager(user) -> bool:
    return effective_role_rank(user) == RoleRank.MANAGER


def _valid_managed_role(role: str) -> bool:
    return role in {
        UserProfile.ROLE_MANAGER,
        UserProfile.ROLE_LIBRARIAN,
        UserProfile.ROLE_READER,
    }


def _can_create_user_with_role(*, actor, role: str) -> bool:
    if not _valid_managed_role(role):
        return False
    if is_owner(actor):
        return True
    if not _is_exact_manager(actor):
        return False
    return role != UserProfile.ROLE_MANAGER


def _can_assign_global_role(*, actor, target_user, new_role: str) -> bool:
    if not _valid_managed_role(new_role):
        return False
    if is_owner(actor):
        return True
    if not _is_exact_manager(actor):
        return False
    if is_owner(target_user):
        return False
    if new_role == UserProfile.ROLE_MANAGER:
        return False
    return not _is_exact_manager(target_user)


def _can_manage_user(*, actor, target_user) -> bool:
    if is_owner(actor):
        return True
    if not _is_exact_manager(actor):
        return False
    if is_owner(target_user):
        return False
    return not _is_exact_manager(target_user)


def can_reset_user_password(*, actor, target_user) -> bool:
    if getattr(actor, "is_anonymous", False):
        return False
    if getattr(actor, "id", None) == getattr(target_user, "id", None):
        return False
    if is_owner(actor):
        return True
    return _can_manage_user(actor=actor, target_user=target_user)

def create_managed_user(
    *,
    actor,
    username: str,
    email: str = "",
    first_name: str = "",
    last_name: str = "",
    role: str = UserProfile.ROLE_READER,
    is_active: bool = True,
) -> ManagedUserCreateResult:
    """
    Create a local Django user for product-managed accounts, with a generated temporary password.

    Rules:
    - Password is generated server-side and returned once to the caller.
    - Password is never stored except via Django's password hash.
    - Role is stored on UserProfile.
    """
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    if not _valid_managed_role(role):
        raise ValidationError({"role": "Invalid role."})

    if not is_manager(actor):
        raise PermissionDenied("Not allowed.")

    if not _can_create_user_with_role(actor=actor, role=role):
        raise PermissionDenied("Not allowed.")

    username = (username or "").strip()
    if not username:
        raise ValidationError({"username": "Username is required."})

    email = (email or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    temporary_password = generate_temporary_password()

    with transaction.atomic():
        try:
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=bool(is_active),
            )
            user.set_password(temporary_password)
            user.full_clean()
            user.save()
        except IntegrityError as exc:
            # Race-safe unique username enforcement (Django auth has unique username by default).
            raise ValidationError({"username": "A user with that username already exists."}) from exc

        profile = get_or_create_profile(user=user)
        profile_updates: dict[str, Any] = {}
        if profile.role != role:
            profile_updates["role"] = role
        if profile.must_change_password is not True:
            profile_updates["must_change_password"] = True
        if profile_updates:
            for key, value in profile_updates.items():
                setattr(profile, key, value)
            profile.full_clean()
            profile.save(update_fields=[*profile_updates.keys(), "updated_at"])

        # Ensure Public group membership via existing service (idempotent).
        ensure_user_public_membership(user=user)

    logger.info(
        "Managed user created: actor=%s target=%s role=%s active=%s",
        user_log_label(actor),
        user_log_label(user),
        role,
        bool(user.is_active),
    )
    return ManagedUserCreateResult(user=user, temporary_password=temporary_password)


def update_user_via_management_api(
    *,
    actor,
    target_user,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    must_change_password: bool | None = None,
) -> UserUpdateResult:
    """
    Safe path for app-level user management (no password handling).

    Rules are enforced via service-local account action helpers plus self-protection.
    """
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    profile = get_or_create_profile(user=target_user)
    was_active = bool(getattr(target_user, "is_active", True))
    old_role = profile.role
    disable_requested = is_active is not None and not bool(is_active)

    user_updates: dict[str, Any] = {}
    profile_updates: dict[str, Any] = {}

    if email is not None:
        if not _can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        value = email.strip()
        if target_user.email != value:
            user_updates["email"] = value

    if first_name is not None:
        if not _can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        value = first_name.strip()
        if target_user.first_name != value:
            user_updates["first_name"] = value

    if last_name is not None:
        if not _can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        value = last_name.strip()
        if target_user.last_name != value:
            user_updates["last_name"] = value

    if is_active is not None:
        if getattr(actor, "id", None) == getattr(target_user, "id", None):
            raise PermissionDenied("Cannot change your own active status.")
        if not _can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        if bool(target_user.is_active) != bool(is_active):
            user_updates["is_active"] = bool(is_active)

    if role is not None:
        if not _valid_managed_role(role):
            raise ValidationError({"role": "Invalid role."})
        if getattr(actor, "id", None) == getattr(target_user, "id", None) and is_manager(actor):
            raise PermissionDenied("Managers cannot change their own role.")
        if not _can_assign_global_role(actor=actor, target_user=target_user, new_role=role):
            raise PermissionDenied("Not allowed.")
        if profile.role != role:
            profile_updates["role"] = role

    if must_change_password is not None:
        if getattr(actor, "id", None) == getattr(target_user, "id", None):
            raise PermissionDenied("Cannot change your own must-change-password flag.")
        if not _can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        if bool(profile.must_change_password) != bool(must_change_password):
            profile_updates["must_change_password"] = bool(must_change_password)

    if not user_updates and not profile_updates and not disable_requested:
        return UserUpdateResult(user=target_user, profile=profile)

    for key, value in user_updates.items():
        setattr(target_user, key, value)
    for key, value in profile_updates.items():
        setattr(profile, key, value)

    with transaction.atomic():
        target_user.full_clean()
        profile.full_clean()
        if user_updates:
            target_user.save(update_fields=[*user_updates.keys()])
        if profile_updates:
            profile.save(update_fields=[*profile_updates.keys(), "updated_at"])
        if disable_requested:
            from accounts import session_control

            counts = session_control.disable_user(target_user, actor=actor)
            info_on_commit(
                logger,
                "Managed user disabled: actor=%s target=%s revoked_web_sessions=%d "
                "revoked_client_sessions=%d",
                user_log_label(actor),
                user_log_label(target_user),
                counts.web_sessions,
                counts.client_sessions,
            )

        changed_fields = sorted([*user_updates.keys(), *profile_updates.keys()])
        if changed_fields:
            info_on_commit(
                logger,
                "Managed user updated: actor=%s target=%s changed_fields=%s role_old=%s "
                "role_new=%s active_old=%s active_new=%s",
                user_log_label(actor),
                user_log_label(target_user),
                ",".join(changed_fields),
                old_role,
                profile.role,
                was_active,
                bool(target_user.is_active),
            )

    return UserUpdateResult(user=target_user, profile=profile)
