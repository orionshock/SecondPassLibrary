from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied

from accounts.request_actor import RequestActorContext
from library.groups.public_group import is_public_group
from library.models import LibraryGroupMembership


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


def build_current_user_me_payload(
    *, user, actor: RequestActorContext
) -> dict[str, Any]:
    memberships = list(
        LibraryGroupMembership.objects.select_related("group")
        .filter(user=user)
        .order_by("group__name", "group__id")
    )

    groups: list[dict[str, Any]] = []
    for membership in memberships:
        group = membership.group
        public = is_public_group(group)
        group_payload: dict[str, Any] = {
            "id": group.id,
            "name": group.name,
            "is_public_group": public,
        }
        if membership.is_curator:
            group_payload["is_curator"] = True
        groups.append(group_payload)

    payload: dict[str, Any] = {
        "username": user.get_username(),
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "profile_id": actor.profile_id,
        "role": actor.role,
        "groups": groups,
    }
    owner = bool(user.is_active and user.is_superuser)
    if actor.must_change_password:
        payload["must_change_password"] = True
    if owner:
        payload["is_owner"] = True
    if owner and settings.SECOND_PASS_ENABLE_DJANGO_ADMIN:
        payload["can_access_django_admin"] = True
    return payload
