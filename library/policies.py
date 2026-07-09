from __future__ import annotations

from accounts import policies as account_policies

from .groups.public_group import is_public_group
from .models import Book, LibraryGroup
from .queries import can_manage_library, can_view_group, visible_books_for_user


def _can_manage_library_groups(user) -> bool:
    return account_policies.is_owner(user) or account_policies.is_manager(user)


def can_import_books(user) -> bool:
    return can_manage_library(user)


def can_view_book(*, user, book: Book) -> bool:
    return visible_books_for_user(user, cached=False).filter(pk=book.pk).exists()


def can_download_book(*, user, book: Book) -> bool:
    return can_view_book(user=user, book=book)


def can_create_library_group(user) -> bool:
    return _can_manage_library_groups(user)


def can_delete_library_group(user, group: LibraryGroup | None = None) -> bool:
    if group is not None and is_public_group(group):
        return False
    return _can_manage_library_groups(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    return _can_manage_library_groups(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    return _can_manage_library_groups(user)


def can_manage_group_books(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_edit_group_presentation(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_edit_group_description(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_view_library_group(*, user, group: LibraryGroup) -> bool:
    return can_view_group(user=user, group=group)


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if is_public_group(group):
        return False
    if user is None or getattr(user, "is_anonymous", False):
        return False
    return group.memberships.filter(user=user, is_curator=True).exists()


def can_add_book_to_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    return can_curate_group(user=user, group=group) and can_view_book(user=user, book=book)


def can_remove_book_from_group(*, user, book: Book, group: LibraryGroup) -> bool:
    return can_manage_library(user) or can_curate_group(user=user, group=group)
