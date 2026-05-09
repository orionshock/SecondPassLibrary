from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.models import AnonymousUser

from accounts.models import UserProfile
from library.models import Book, BookFile, ImportJob, LibraryGroup
from library.models import LibraryGroupMembership
from library.models import is_public_group


def is_owner(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _get_profile(user) -> UserProfile | None:
    if user is None or isinstance(user, AnonymousUser) or getattr(user, "is_anonymous", False):
        return None
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return None


def _profile_role(user) -> str | None:
    profile = _get_profile(user)
    return profile.role if profile is not None else None


def _is_manager_role(user) -> bool:
    return _profile_role(user) == UserProfile.ROLE_MANAGER


def _is_librarian_role(user) -> bool:
    return _profile_role(user) == UserProfile.ROLE_LIBRARIAN


def is_manager(user) -> bool:
    if is_owner(user):
        return True
    return _is_manager_role(user)


def is_librarian(user) -> bool:
    if is_owner(user):
        return True
    return _is_librarian_role(user)


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
    if new_role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
        return False

    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    # Managers cannot edit Owner accounts.
    if is_owner(target_user):
        return False

    # Only Owner can promote to Manager.
    if new_role == UserProfile.ROLE_MANAGER:
        return False

    # Only Owner can demote existing Managers.
    if _is_manager_role(target_user):
        return False

    return True


def can_manage_user(*, actor, target_user) -> bool:
    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    if is_owner(target_user):
        return False

    # Managers cannot manage other Managers.
    if _is_manager_role(target_user):
        return False

    return True


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


def can_create_library_group(user) -> bool:
    return is_owner(user) or _is_manager_role(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    if is_public_group(group):
        return False
    return is_owner(user) or _is_manager_role(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    # Membership management is an app-admin operation, not a librarian/curator operation.
    return is_owner(user) or _is_manager_role(user)


def can_edit_group_presentation(*, user, group: LibraryGroup) -> bool:
    # Group presentation is limited to description only.
    # Public is handled by field-specific helpers.
    if is_public_group(group):
        return False
    if is_owner(user) or _is_manager_role(user) or _is_librarian_role(user):
        return True
    return LibraryGroupMembership.objects.filter(
        user=user, group=group, role=LibraryGroupMembership.ROLE_CURATOR
    ).exists()


def can_edit_group_description(*, user, group: LibraryGroup) -> bool:
    if is_public_group(group):
        return is_owner(user) or _is_manager_role(user) or _is_librarian_role(user)
    return can_edit_group_presentation(user=user, group=group)


def can_view_library_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if getattr(user, "is_anonymous", False):
        return False
    if is_public_group(group):
        return True
    return LibraryGroupMembership.objects.filter(user=user, group=group).exists()


def can_manage_library_group(*, user, group: LibraryGroup) -> bool:
    # Legacy helper retained for call sites; use more specific helpers for new code.
    return can_manage_library(user)


def can_curate_group(*, user, group: LibraryGroup) -> bool:
    if is_public_group(group):
        return False
    return LibraryGroupMembership.objects.filter(
        user=user, group=group, role=LibraryGroupMembership.ROLE_CURATOR
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
