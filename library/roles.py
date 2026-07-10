from __future__ import annotations

from enum import IntEnum

from accounts.models import UserProfile
from accounts import policies as account_policies

from library.groups.public_group import is_public_group
from library.models import LibraryGroup


class RoleRank(IntEnum):
    READER = 0
    LIBRARIAN = 10
    MANAGER = 20
    OWNER = 30


def effective_role_rank(user) -> RoleRank:
    if account_policies.is_owner(user):
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


def is_curator(user, group: LibraryGroup) -> bool:
    if effective_role_rank(user) >= RoleRank.LIBRARIAN:
        return True
    if user is None or getattr(user, "is_anonymous", False):
        return False
    if is_public_group(group):
        return False
    return group.memberships.filter(user=user, is_curator=True).exists()


def _profile_role(user) -> str | None:
    if user is None or getattr(user, "is_anonymous", False):
        return None
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return None
