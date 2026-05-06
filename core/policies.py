from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.models import AnonymousUser

from accounts.models import UserProfile
from library.models import Book, BookFile, ImportJob, LibraryGroup
from library.models import LibraryGroupMembership


def is_owner(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _get_profile(user) -> UserProfile | None:
    if user is None or isinstance(user, AnonymousUser) or getattr(user, "is_anonymous", False):
        return None
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return None


def is_manager(user) -> bool:
    if is_owner(user):
        return True
    profile = _get_profile(user)
    return bool(profile and profile.role == UserProfile.ROLE_MANAGER)


def is_librarian(user) -> bool:
    if is_owner(user):
        return True
    profile = _get_profile(user)
    return bool(profile and profile.role == UserProfile.ROLE_LIBRARIAN)


def is_reader(user) -> bool:
    if user is None or getattr(user, "is_anonymous", False):
        return False
    if is_owner(user) or is_manager(user) or is_librarian(user):
        return True
    profile = _get_profile(user)
    # Missing profile should behave like reader for now.
    return bool(profile is None or profile.role == UserProfile.ROLE_READER)


def can_manage_users(user) -> bool:
    return is_owner(user) or is_manager(user)


def can_assign_global_role(*, actor, target_user, new_role: str) -> bool:
    if is_owner(actor):
        return True
    if not is_manager(actor):
        return False
    # Manager can assign librarian/reader, but not manager.
    return new_role in {UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}


def can_manage_library(user) -> bool:
    return is_owner(user) or is_manager(user) or is_librarian(user)


def can_import_books(user) -> bool:
    return can_manage_library(user)


def can_view_book(*, user, book: Book) -> bool:
    if is_owner(user) or is_manager(user) or is_librarian(user):
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


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if group.is_public:
        return False
    return LibraryGroupMembership.objects.filter(
        user=user, group=group, role=LibraryGroupMembership.ROLE_CURATOR
    ).exists()


def can_add_book_to_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if group.is_public:
        return False
    if not can_curate_group(user=user, group=group):
        return False
    # Curator can only add books they can already view.
    return can_view_book(user=user, book=book)


def can_remove_book_from_group(*, user, book: Book, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if group.is_public:
        return False
    return can_curate_group(user=user, group=group)


def _owner_id_from_obj(obj: Any):
    if hasattr(obj, "user_id"):
        return getattr(obj, "user_id")
    if hasattr(obj, "user"):
        return getattr(getattr(obj, "user"), "id", None)
    if hasattr(obj, "session") and hasattr(obj.session, "user_id"):
        return getattr(obj.session, "user_id")
    return None


def can_view_reading_metadata(*, user, obj: Any) -> bool:
    if getattr(user, "is_anonymous", False):
        return False
    owner_id = _owner_id_from_obj(obj)
    return owner_id == getattr(user, "id", None)


def can_edit_reading_metadata(*, user, obj: Any) -> bool:
    return can_view_reading_metadata(user=user, obj=obj)
