from __future__ import annotations

from typing import Any, cast

from accounts import policies as account_policies

from .models import Book, BookFile, ImportJob, LibraryGroup, LibraryGroupMembership
from .models import is_public_group


def can_manage_library(user) -> bool:
    return (
        account_policies.is_owner(user)
        or account_policies.is_manager(user)
        or account_policies.is_librarian(user)
    )


def can_import_books(user) -> bool:
    return can_manage_library(user)


def can_view_book(*, user, book: Book) -> bool:
    if (
        account_policies.is_owner(user)
        or account_policies.is_manager(user)
        or account_policies.is_librarian(user)
    ):
        return True
    if getattr(user, "is_anonymous", False):
        return False
    group_assignments = cast(Any, getattr(book, "group_assignments"))
    return group_assignments.filter(group__memberships__user=user).exists()


def can_download_book_file(*, user, book_file: BookFile) -> bool:
    return can_view_book(user=user, book=book_file.book)


def can_view_import_job(*, user, import_job: ImportJob) -> bool:
    if can_manage_library(user):
        return True
    import_job_user_id = getattr(import_job, "user_id", None)
    return bool(import_job_user_id == getattr(user, "id", None))


def can_manage_import_job(*, user, import_job: ImportJob) -> bool:
    return can_manage_library(user)


def can_create_library_group(user) -> bool:
    return account_policies.is_manager(user)


def can_delete_library_group(user, group: LibraryGroup | None = None) -> bool:
    if group is not None and is_public_group(group):
        return False
    return can_create_library_group(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    if is_public_group(group):
        return False
    return account_policies.is_manager(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    # Membership management is an app-admin operation, not a librarian/curator operation.
    return account_policies.is_manager(user)


def can_manage_group_books(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_edit_group_presentation(*, user, group: LibraryGroup) -> bool:
    # Group presentation is limited to description only.
    return can_curate_group(user=user, group=group)


def can_edit_group_description(*, user, group: LibraryGroup) -> bool:
    return can_curate_group(user=user, group=group)


def can_view_library_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if getattr(user, "is_anonymous", False):
        return False
    if is_public_group(group):
        return True
    return LibraryGroupMembership.objects.filter(user=user, group=group).exists()


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if is_public_group(group):
        return False
    return LibraryGroupMembership.objects.filter(
        user=user, group=group, is_curator=True
    ).exists()


def can_add_book_to_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if is_public_group(group):
        return False
    if not can_curate_group(user=user, group=group):
        return False
    # Curator can only add books they can already view.
    return can_view_book(user=user, book=book)


def can_remove_book_from_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if is_public_group(group):
        return False
    return can_curate_group(user=user, group=group)
