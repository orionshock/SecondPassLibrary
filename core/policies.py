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


def can_create_user_with_role(*, actor, role: str) -> bool:
    """
    Permission check for creating a new user with a given global role.

    Notes:
    - Uses the same high-level role rules as can_assign_global_role, but since a
      target user does not exist yet, the check is based on the actor + desired role.
    """
    if role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
        return False

    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    # Only Owner can create Managers.
    if role == UserProfile.ROLE_MANAGER:
        return False

    return True


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


def can_reset_user_password(*, actor, target_user) -> bool:
    """
    Password reset via managed endpoint (not self-service).

    Rules:
    - Managers can reset Librarian/Reader only (never Owner/Manager).
    - Owners can reset Manager/Librarian/Reader (never self via managed reset).
    """
    if getattr(actor, "is_anonymous", False):
        return False
    if getattr(actor, "id", None) == getattr(target_user, "id", None):
        return False
    if is_owner(actor):
        return True
    return can_manage_user(actor=actor, target_user=target_user)


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


def can_delete_library_group(user, group: LibraryGroup | None = None) -> bool:
    if group is not None and is_public_group(group):
        return False
    return can_create_library_group(user)


def can_manage_group_identity(*, user, group: LibraryGroup) -> bool:
    if is_public_group(group):
        return False
    return is_owner(user) or _is_manager_role(user)


def can_manage_group_membership(*, user, group: LibraryGroup) -> bool:
    # Membership management is an app-admin operation, not a librarian/curator operation.
    return is_owner(user) or _is_manager_role(user)


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
