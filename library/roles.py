from __future__ import annotations

from accounts.roles import RoleRank, effective_role_rank

from library.groups.public_group import is_public_group
from library.models import LibraryGroup


def is_curator(user, group: LibraryGroup) -> bool:
    if effective_role_rank(user) >= RoleRank.LIBRARIAN:
        return True
    if user is None or getattr(user, "is_anonymous", False):
        return False
    if is_public_group(group):
        return False
    return group.memberships.filter(user=user, is_curator=True).exists()
