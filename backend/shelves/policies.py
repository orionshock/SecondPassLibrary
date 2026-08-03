from __future__ import annotations

from django.db.models import QuerySet

from accounts.models import UserClientSession
from accounts.roles import is_librarian
from library.groups.public_group import is_public_group
from library.models import Book
from library.queries import visible_books_for_group, visible_books_for_user
from library.roles import is_curator

from .models import Shelf


def can_create_shelf(
    *,
    user,
    owner_type: str,
    owner_user=None,
    owner_group=None,
) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if owner_type == Shelf.OWNER_TYPE_USER:
        target_user = owner_user or user
        return getattr(target_user, "id", None) == getattr(user, "id", None)

    if owner_type == Shelf.OWNER_TYPE_GROUP:
        if owner_group is None:
            return False
        if is_librarian(user):
            return True
        if is_public_group(owner_group):
            return False
        return is_curator(user, owner_group)

    return False


def can_edit_shelf(*, user, shelf: Shelf) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        return shelf.owner_user_id == getattr(user, "id", None)

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        group = shelf.owner_group
        return group is not None and can_create_shelf(
            user=user,
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )

    return False


def request_can_edit_shelf(*, request, shelf: Shelf) -> bool:
    user = getattr(request, "user", None)
    if user is None:
        return False

    if isinstance(getattr(request, "auth", None), UserClientSession):
        return (
            shelf.owner_type == Shelf.OWNER_TYPE_USER
            and shelf.owner_user_id == getattr(user, "id", None)
        )

    return can_edit_shelf(user=user, shelf=shelf)


def visible_books_for_shelf(*, user, shelf: Shelf) -> QuerySet[Book]:
    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        return visible_books_for_user(user, cached=False)

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP and shelf.owner_group is not None:
        return visible_books_for_group(user, shelf.owner_group, cached=False)

    return Book.objects.none()


def books_available_to_shelf_editor(*, user, shelf: Shelf) -> QuerySet[Book]:
    if not can_edit_shelf(user=user, shelf=shelf):
        return Book.objects.none()
    return visible_books_for_shelf(user=user, shelf=shelf)
