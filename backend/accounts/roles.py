from __future__ import annotations

from enum import IntEnum

from accounts.models import UserProfile


class RoleRank(IntEnum):
    READER = 0
    LIBRARIAN = 10
    MANAGER = 20
    OWNER = 30


def effective_role_rank(user) -> RoleRank:
    if user is None or getattr(user, "is_anonymous", False):
        return RoleRank.READER
    if not getattr(user, "is_active", True):
        return RoleRank.READER
    if getattr(user, "is_superuser", False):
        return RoleRank.OWNER
    role = _profile_role(user)
    if role == UserProfile.ROLE_MANAGER:
        return RoleRank.MANAGER
    if role == UserProfile.ROLE_LIBRARIAN:
        return RoleRank.LIBRARIAN
    return RoleRank.READER


def is_owner(user) -> bool:
    return effective_role_rank(user) >= RoleRank.OWNER


def is_manager(user) -> bool:
    return effective_role_rank(user) >= RoleRank.MANAGER


def is_librarian(user) -> bool:
    return effective_role_rank(user) >= RoleRank.LIBRARIAN


def _profile_role(user) -> str | None:
    try:
        return user.profile.role
    except (AttributeError, UserProfile.DoesNotExist):
        return None
