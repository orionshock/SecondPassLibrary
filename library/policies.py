from __future__ import annotations

from accounts.roles import is_librarian, is_manager

from .groups.public_group import is_public_group
from .models import Book, LibraryGroup
from .queries import can_view_group, visible_books_for_user
from .roles import is_curator


def can_import_books(user) -> bool:
    return is_librarian(user)


def can_view_book(*, user, book: Book) -> bool:
    return visible_books_for_user(user, cached=False).filter(pk=book.pk).exists()


def can_download_book(*, user, book: Book) -> bool:
    return can_view_book(user=user, book=book)


def can_create_library_group(user) -> bool:
    return is_manager(user)


def can_delete_library_group(user, group: LibraryGroup | None = None) -> bool:
    if group is not None and is_public_group(group):
        return False
    return is_manager(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    return is_manager(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    return is_manager(user)


def can_manage_group_books(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_edit_group_presentation(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_edit_group_description(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_view_library_group(*, user, group: LibraryGroup) -> bool:
    return can_view_group(user=user, group=group)


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    return is_curator(user, group)


def can_add_book_to_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if is_librarian(user):
        return True
    return can_curate_group(user=user, group=group) and can_view_book(user=user, book=book)


def can_remove_book_from_group(*, user, book: Book, group: LibraryGroup) -> bool:
    return is_librarian(user) or can_curate_group(user=user, group=group)
