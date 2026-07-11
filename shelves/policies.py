from __future__ import annotations

from django.db.models import Q

from accounts.models import UserClientSession
from accounts.roles import is_librarian
from library.models import Book, LibraryGroupMembership
from library.queries import visible_books_for_group, visible_books_for_user
from library.groups.public_group import is_public_group
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


def visible_shelf_filter(user) -> Q:
    if getattr(user, "is_anonymous", False):
        return Q(pk__isnull=True)

    user_shelves = Q(owner_type=Shelf.OWNER_TYPE_USER, owner_user=user) | Q(
        owner_type=Shelf.OWNER_TYPE_USER,
        visibility=Shelf.VISIBILITY_LISTED,
    )
    group_shelves = Q(
        owner_type=Shelf.OWNER_TYPE_GROUP,
        owner_group__memberships__user=user,
    )
    if is_librarian(user):
        group_shelves = Q(owner_type=Shelf.OWNER_TYPE_GROUP)

    return user_shelves | group_shelves


def can_view_shelf(*, user, shelf: Shelf) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        owner_user_id = getattr(shelf, "owner_user_id", None)
        if owner_user_id == getattr(user, "id", None):
            return True
        return shelf.visibility == Shelf.VISIBILITY_LISTED

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        if is_librarian(user):
            return True
        group = shelf.owner_group
        if group is None:
            return False
        return LibraryGroupMembership.objects.filter(user=user, group=group).exists()

    return False


def can_edit_shelf(*, user, shelf: Shelf) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        owner_user_id = getattr(shelf, "owner_user_id", None)
        return owner_user_id == getattr(user, "id", None)

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        group = shelf.owner_group
        if group is None:
            return False
        return can_create_shelf(
            user=user,
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )

    return False


def can_client_bearer_edit_shelf(*, user, shelf: Shelf) -> bool:
    """
    Client API bearer tokens may only edit personal shelves owned by the token user.

    This helper is intentionally narrower than can_edit_shelf (which includes
    group-shelf edit rules for session-authenticated product UI users).
    """
    if user is None or getattr(user, "is_anonymous", False):
        return False
    if shelf.owner_type != Shelf.OWNER_TYPE_USER:
        return False
    return getattr(shelf, "owner_user_id", None) == getattr(user, "id", None)


def can_edit_shelf_for_request(*, request, shelf: Shelf) -> bool:
    user = getattr(request, "user", None)
    if user is None:
        return False
    if isinstance(getattr(request, "auth", None), UserClientSession):
        return can_client_bearer_edit_shelf(user=user, shelf=shelf)
    return can_edit_shelf(user=user, shelf=shelf)


def can_add_book_to_shelf(*, user, book: Book, shelf: Shelf) -> bool:
    if not can_edit_shelf(user=user, shelf=shelf):
        return False

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        return visible_books_for_user(user, cached=False).filter(pk=book.pk).exists()

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        group = shelf.owner_group
        if group is None:
            return False
        return visible_books_for_group(user, group, cached=False).filter(pk=book.pk).exists()

    return False


def can_remove_book_from_shelf(*, user, book: Book, shelf: Shelf) -> bool:
    return can_edit_shelf(user=user, shelf=shelf)
