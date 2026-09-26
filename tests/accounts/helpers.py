from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from tests.utils.users import create_role_users, set_user_role


User = get_user_model()


@dataclass(frozen=True)
class AccountRoleUsers:
    owner: object
    manager: object
    manager2: object
    librarian: object
    reader: object


def create_account_role_users() -> AccountRoleUsers:
    role_users = create_role_users()
    manager2 = User.objects.create_user(
        username="manager2",
        password="pw",
        email="manager2@example.com",
    )

    set_user_role(manager2, UserProfile.ROLE_MANAGER)

    return AccountRoleUsers(
        owner=role_users.owner,
        manager=role_users.manager,
        manager2=manager2,
        librarian=role_users.librarian,
        reader=role_users.reader,
    )
