from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from core import policies

from .models import UserProfile


User = get_user_model()


@dataclass(frozen=True)
class UserUpdateResult:
    user: Any
    profile: UserProfile


def get_or_create_profile(*, user) -> UserProfile:
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def update_user_via_management_api(
    *,
    actor,
    target_user,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
) -> UserUpdateResult:
    """
    Safe path for app-level user management (no password handling).

    Rules are enforced via core.policies helpers plus a small amount of self-protection.
    """
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    profile = get_or_create_profile(user=target_user)

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

    if not user_updates and not profile_updates:
        return UserUpdateResult(user=target_user, profile=profile)

    if user_updates:
        for key, value in user_updates.items():
            setattr(target_user, key, value)
        target_user.full_clean()
        target_user.save(update_fields=[*user_updates.keys()])

    if profile_updates:
        for key, value in profile_updates.items():
            setattr(profile, key, value)
        profile.full_clean()
        profile.save(update_fields=[*profile_updates.keys(), "updated_at"])

    return UserUpdateResult(user=target_user, profile=profile)

