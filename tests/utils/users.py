from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from accounts.models import UserProfile


User = get_user_model()


def set_user_role(user, role: str) -> None:
    profile = user.profile
    profile.role = role
    profile.save(update_fields=["role", "updated_at"])


@dataclass(frozen=True)
class RoleUsers:
    owner: object
    manager: object
    librarian: object
    reader: object


def create_role_users(*, reader_email: str = "") -> RoleUsers:
    owner = User.objects.create_superuser(
        username="owner",
        password="pw",
        email="owner@example.com",
    )
    manager = User.objects.create_user(
        username="manager",
        password="pw",
        email="manager@example.com",
    )
    librarian = User.objects.create_user(
        username="librarian",
        password="pw",
        email="librarian@example.com",
    )
    reader = User.objects.create_user(
        username="reader",
        password="pw",
        email=reader_email,
    )

    set_user_role(manager, UserProfile.ROLE_MANAGER)
    set_user_role(librarian, UserProfile.ROLE_LIBRARIAN)
    set_user_role(reader, UserProfile.ROLE_READER)

    return RoleUsers(
        owner=owner,
        manager=manager,
        librarian=librarian,
        reader=reader,
    )
