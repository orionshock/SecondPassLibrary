from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from accounts.models import UserProfile


User = get_user_model()


def set_role(user, role: str) -> None:
    profile = user.profile
    profile.role = role
    profile.save(update_fields=["role", "updated_at"])


@dataclass(frozen=True)
class AccountRoleUsers:
    owner: object
    manager: object
    manager2: object
    librarian: object
    reader: object


def create_account_role_users() -> AccountRoleUsers:
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
    manager2 = User.objects.create_user(
        username="manager2",
        password="pw",
        email="manager2@example.com",
    )
    librarian = User.objects.create_user(
        username="librarian",
        password="pw",
        email="librarian@example.com",
    )
    reader = User.objects.create_user(
        username="reader",
        password="pw",
    )

    set_role(manager, UserProfile.ROLE_MANAGER)
    set_role(manager2, UserProfile.ROLE_MANAGER)
    set_role(librarian, UserProfile.ROLE_LIBRARIAN)
    set_role(reader, UserProfile.ROLE_READER)

    return AccountRoleUsers(
        owner=owner,
        manager=manager,
        manager2=manager2,
        librarian=librarian,
        reader=reader,
    )
