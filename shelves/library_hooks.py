from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


SHELVES_GROUP_BOOK_REMOVAL_PENDING_MESSAGE = (
    "LibraryReWrite2607 shelves reconnect required: removing a book from a group "
    "must remove it from shelves owned by that group."
)


def remove_book_from_group_owned_shelves(*, book, group) -> None:
    raise ImproperlyConfigured(SHELVES_GROUP_BOOK_REMOVAL_PENDING_MESSAGE)
