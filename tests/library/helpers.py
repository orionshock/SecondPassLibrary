from __future__ import annotations

from django.contrib.auth.models import User

from accounts.models import UserProfile
from library.groups.services import ensure_user_public_membership


def _create_user_with_role(*, username, password="pw", role=UserProfile.ROLE_READER, **kwargs):
    user = User.objects.create_user(username=username, password=password, **kwargs)
    ensure_user_public_membership(user=user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = role
    profile.save(update_fields=["role", "updated_at"])
    return user


def create_reader_user(username="reader", password="pw", **kwargs):
    return _create_user_with_role(
        username=username,
        password=password,
        role=UserProfile.ROLE_READER,
        **kwargs,
    )


def create_librarian_user(username="librarian", password="pw", **kwargs):
    return _create_user_with_role(
        username=username,
        password=password,
        role=UserProfile.ROLE_LIBRARIAN,
        **kwargs,
    )


def create_manager_user(username="manager", password="pw", **kwargs):
    return _create_user_with_role(
        username=username,
        password=password,
        role=UserProfile.ROLE_MANAGER,
        **kwargs,
    )


def create_owner_user(username="owner", password="pw", **kwargs):
    user = User.objects.create_superuser(username=username, password=password, **kwargs)
    ensure_user_public_membership(user=user)
    return user
