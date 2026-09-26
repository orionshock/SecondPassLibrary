from __future__ import annotations

from library.groups.memberships import ensure_user_public_membership
from library.groups.book_assignments import ensure_book_public_assignment


def ensure_public_membership(user):
    return ensure_user_public_membership(user=user)


def ensure_public_book_assignment(book, *, actor=None):
    return ensure_book_public_assignment(book=book, added_by=actor)
