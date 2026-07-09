from __future__ import annotations

from .models import Book, LibraryGroup
from .queries import can_manage_library, can_view_group, visible_books_for_user


def can_import_books(user) -> bool:
    return can_manage_library(user)


def can_view_book(*, user, book: Book) -> bool:
    return visible_books_for_user(user, cached=False).filter(pk=book.pk).exists()


def can_download_book(*, user, book: Book) -> bool:
    return can_view_book(user=user, book=book)


def can_download_book_file(*, user, book_file) -> bool:
    # LibraryReWrite2607 temporary alias for old downstream imports. Download/open
    # policy should take Book directly when that path is reconnected.
    book = getattr(book_file, "book", None) or book_file
    return can_download_book(user=user, book=book)


def can_create_library_group(user) -> bool:
    return can_manage_library(user)


def can_delete_library_group(user, group: LibraryGroup | None = None) -> bool:
    return can_manage_library(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    return can_manage_library(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    return can_manage_library(user)


def can_manage_group_books(*, user, group: LibraryGroup) -> bool:
    return can_manage_library(user)


def can_edit_group_presentation(*, user, group: LibraryGroup) -> bool:
    return can_manage_library(user)


def can_edit_group_description(*, user, group: LibraryGroup) -> bool:
    return can_manage_library(user)


def can_view_library_group(*, user, group: LibraryGroup) -> bool:
    return can_view_group(user=user, group=group)


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if user is None or getattr(user, "is_anonymous", False):
        return False
    return group.memberships.filter(user=user, is_curator=True).exists()


def can_add_book_to_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    return can_curate_group(user=user, group=group) and can_view_book(user=user, book=book)


def can_remove_book_from_group(*, user, book: Book, group: LibraryGroup) -> bool:
    return can_manage_library(user) or can_curate_group(user=user, group=group)
