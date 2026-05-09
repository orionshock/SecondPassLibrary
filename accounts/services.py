from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from core import policies
from library.models import LibraryGroupMembership, is_public_group

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


def build_current_user_me_payload(*, user) -> dict[str, Any]:
    profile = get_or_create_profile(user=user)

    memberships = list(
        LibraryGroupMembership.objects.select_related("group")
        .filter(user=user)
        .order_by("group__name", "group__slug")
    )

    groups: list[dict[str, Any]] = []
    curated_group_ids: list[Any] = []
    for membership in memberships:
        group = membership.group
        public = is_public_group(group)
        groups.append(
            {
                "id": group.id,
                "name": group.name,
                "slug": group.slug,
                "discoverability": group.discoverability,
                "membership_role": membership.role,
                "is_public_group": public,
            }
        )
        if (
            membership.role == LibraryGroupMembership.ROLE_CURATOR
            and not public
        ):
            curated_group_ids.append(group.id)

    can_manage_users = policies.can_manage_users(user)
    can_manage_library = policies.can_manage_library(user)
    can_import_books = policies.can_import_books(user)
    can_create_library_groups = policies.can_create_library_group(user)

    capabilities = {
        "can_manage_users": can_manage_users,
        "can_manage_library": can_manage_library,
        "can_import_books": can_import_books,
        "can_create_library_groups": can_create_library_groups,
        "can_manage_group_memberships": can_manage_users,
        "can_manage_group_identity": can_manage_users,
        "can_edit_group_presentation": bool(can_manage_library or curated_group_ids),
        "can_access_imports": bool(can_import_books or can_manage_library),
    }

    return {
        "username": user.get_username(),
        "email": user.email or "",
        "profile_id": profile.id,
        "role": profile.role,
        "is_owner": policies.is_owner(user),
        "capabilities": capabilities,
        "groups": groups,
        "curated_group_ids": curated_group_ids,
    }
