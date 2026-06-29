from __future__ import annotations

from typing import Any

from core import policies
from library.models import LibraryGroupMembership, is_public_group

from .services import ManagedUserCreateResult, get_or_create_profile


def managed_user_group_payloads(user) -> list[dict[str, Any]]:
    memberships = list(
        getattr(user, "library_group_memberships", LibraryGroupMembership.objects.none())
        .all()
    )
    groups = []
    for membership in memberships:
        group = membership.group
        groups.append(
            {
                "membership_id": membership.id,
                "id": group.id,
                "name": group.name,
                "is_public_group": is_public_group(group),
                "is_curator": bool(membership.is_curator),
            }
        )
    return sorted(groups, key=lambda g: (g["name"], str(g["id"])))


def compact_user_payload(user) -> dict[str, Any]:
    profile = get_or_create_profile(user=user)
    return {
        "profile_id": profile.id,
        "username": user.get_username(),
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
    }


def managed_user_payload(user) -> dict[str, Any]:
    profile = get_or_create_profile(user=user)
    return {
        "profile_id": profile.id,
        "username": user.get_username(),
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_active": bool(getattr(user, "is_active", True)),
        "date_joined": user.date_joined,
        "last_login": user.last_login,
        "is_owner": policies.is_owner(user),
        "role": profile.role,
        "must_change_password": bool(profile.must_change_password),
        "groups": managed_user_group_payloads(user),
    }


def managed_user_create_envelope(result: ManagedUserCreateResult) -> dict[str, Any]:
    return {
        "user": managed_user_payload(result.user),
        "temporary_password": result.temporary_password,
        "message": "Show this password now. It will not be shown again.",
    }
