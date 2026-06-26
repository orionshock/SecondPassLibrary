from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.db import IntegrityError, transaction

from core import policies
from library.group_services import ensure_user_public_membership
from library.models import LibraryGroupMembership, is_public_group

from .models import UserProfile


User = get_user_model()


@dataclass(frozen=True)
class UserUpdateResult:
    user: Any
    profile: UserProfile


@dataclass(frozen=True)
class ManagedUserCreateResult:
    user: Any
    temporary_password: str


@dataclass(frozen=True)
class ManagedPasswordResetResult:
    username: str
    temporary_password: str

    @property
    def copy_block(self) -> str:
        return f"Username: {self.username}\nPassword: {self.temporary_password}"


def get_or_create_profile(*, user) -> UserProfile:
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def user_supports_local_password(user) -> bool:
    if not user or getattr(user, "is_anonymous", False):
        return False
    has_usable_password = getattr(user, "has_usable_password", None)
    return bool(callable(has_usable_password) and has_usable_password())


def _generate_temporary_password() -> str:
    # Short, URL-safe, cryptographically secure; shown once on create response only.
    return secrets.token_urlsafe(18)


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

    if role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
        raise ValidationError({"role": "Invalid role."})

    if not policies.can_manage_users(actor):
        raise PermissionDenied("Not allowed.")

    if not policies.can_create_user_with_role(actor=actor, role=role):
        raise PermissionDenied("Not allowed.")

    username = (username or "").strip()
    if not username:
        raise ValidationError({"username": "Username is required."})

    email = (email or "").strip()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    temporary_password = _generate_temporary_password()

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

    Rules are enforced via core.policies helpers plus a small amount of self-protection.
    """
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    profile = get_or_create_profile(user=target_user)
    was_active = bool(getattr(target_user, "is_active", True))

    user_updates: dict[str, Any] = {}
    profile_updates: dict[str, Any] = {}

    if email is not None:
        if not policies.can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        user_updates["email"] = email

    if first_name is not None:
        if not policies.can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        user_updates["first_name"] = first_name

    if last_name is not None:
        if not policies.can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        user_updates["last_name"] = last_name

    if is_active is not None:
        if getattr(actor, "id", None) == getattr(target_user, "id", None):
            raise PermissionDenied("Cannot change your own active status.")
        if not policies.can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        user_updates["is_active"] = is_active

    if role is not None:
        if role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
            raise ValidationError({"role": "Invalid role."})
        if getattr(actor, "id", None) == getattr(target_user, "id", None) and policies.is_manager(actor):
            raise PermissionDenied("Managers cannot change their own role.")
        if not policies.can_assign_global_role(actor=actor, target_user=target_user, new_role=role):
            raise PermissionDenied("Not allowed.")
        profile_updates["role"] = role

    if must_change_password is not None:
        if getattr(actor, "id", None) == getattr(target_user, "id", None):
            raise PermissionDenied("Cannot change your own must-change-password flag.")
        if not policies.can_manage_user(actor=actor, target_user=target_user):
            raise PermissionDenied("Not allowed.")
        profile_updates["must_change_password"] = bool(must_change_password)

    if not user_updates and not profile_updates:
        return UserUpdateResult(user=target_user, profile=profile)

    if user_updates:
        for key, value in user_updates.items():
            setattr(target_user, key, value)
        target_user.full_clean()
        target_user.save(update_fields=[*user_updates.keys()])

        # If a user is being disabled, revoke all their web sessions.
        # Re-enabling does not restore sessions.
        if "is_active" in user_updates and user_updates.get("is_active") is False and was_active is True:
            from accounts import session_control

            session_control.disable_user(target_user)

    if profile_updates:
        for key, value in profile_updates.items():
            setattr(profile, key, value)
        profile.full_clean()
        profile.save(update_fields=[*profile_updates.keys(), "updated_at"])

    return UserUpdateResult(user=target_user, profile=profile)


def update_current_user_via_me_api(
    *,
    user,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> None:
    """
    Safe path for a user to update their own basic contact/profile fields via /accounts/me/.

    Intentionally limited:
    - Allows: email, first_name, last_name
    - Disallows: username, role, is_active, password, and all auth internals
    """
    if getattr(user, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    updates: dict[str, Any] = {}
    if email is not None:
        updates["email"] = email
    if first_name is not None:
        updates["first_name"] = first_name
    if last_name is not None:
        updates["last_name"] = last_name

    if not updates:
        return

    for key, value in updates.items():
        setattr(user, key, value)
    user.full_clean()
    user.save(update_fields=[*updates.keys()])


def _validate_new_password(*, new_password: str, user) -> None:
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


def change_current_user_password(
    *,
    user,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    if getattr(user, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    if not (current_password or ""):
        raise ValidationError({"current_password": "Current password is required."})

    if not user.check_password(current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})

    if (new_password or "") != (confirm_password or ""):
        raise ValidationError({"confirm_password": "Passwords do not match."})

    _validate_new_password(new_password=new_password, user=user)
    if (new_password or "") == (current_password or ""):
        raise ValidationError({"new_password": "New password must be different from current password."})

    user.set_password(new_password)
    user.full_clean()
    user.save(update_fields=["password"])

    profile = get_or_create_profile(user=user)
    if profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password", "updated_at"])


def reset_managed_user_password(
    *,
    actor,
    target_user,
) -> ManagedPasswordResetResult:
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    if getattr(actor, "id", None) == getattr(target_user, "id", None):
        raise PermissionDenied("Cannot reset your own password here.")

    if not policies.can_reset_user_password(actor=actor, target_user=target_user):
        raise PermissionDenied("Not allowed.")

    temporary_password = _generate_temporary_password()

    with transaction.atomic():
        target_user.set_password(temporary_password)
        target_user.full_clean()
        target_user.save(update_fields=["password"])

        profile = get_or_create_profile(user=target_user)
        if profile.must_change_password is not True:
            profile.must_change_password = True
            profile.full_clean()
            profile.save(update_fields=["must_change_password", "updated_at"])

    return ManagedPasswordResetResult(
        username=target_user.get_username(),
        temporary_password=temporary_password,
    )


def build_current_user_me_payload(*, user) -> dict[str, Any]:
    profile = get_or_create_profile(user=user)

    memberships = list(
        LibraryGroupMembership.objects.select_related("group")
        .filter(user=user)
        .order_by("group__name", "group__id")
    )

    groups: list[dict[str, Any]] = []
    for membership in memberships:
        group = membership.group
        public = is_public_group(group)
        groups.append(
            {
                "id": group.id,
                "name": group.name,
                "is_public_group": public,
                "is_curator": bool(membership.is_curator),
            }
        )

    can_manage_users = policies.can_manage_users(user)
    can_manage_library = policies.can_manage_library(user)
    can_import_books = policies.can_import_books(user)
    can_create_library_groups = policies.can_create_library_group(user)
    has_curated_groups = any(
        bool(group["is_curator"]) and not bool(group["is_public_group"]) for group in groups
    )

    capabilities = {
        "can_manage_users": can_manage_users,
        "can_manage_library": can_manage_library,
        "can_import_books": can_import_books,
        "can_create_library_groups": can_create_library_groups,
        "can_manage_group_memberships": can_manage_users,
        "can_manage_group_identity": can_manage_users,
        "can_edit_group_presentation": bool(can_manage_library or has_curated_groups),
        "can_access_imports": bool(can_import_books or can_manage_library),
    }

    return {
        "username": user.get_username(),
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "profile_id": profile.id,
        "role": profile.role,
        "must_change_password": bool(profile.must_change_password),
        "is_owner": policies.is_owner(user),
        "capabilities": capabilities,
        "groups": groups,
    }
