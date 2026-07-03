from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from library import policies
from core.server_settings import get_server_setting, set_server_setting
from .models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership, is_public_group

PUBLIC_GROUP_ID_SETTING = "public_group_id"
DEFAULT_PUBLIC_GROUP_NAME = "Common Room"
DEFAULT_PUBLIC_GROUP_DESCRIPTION = "Main Public Library Room for everyone"


def _parse_uuid_setting_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return str(uuid.UUID(s))
        except (ValueError, AttributeError, TypeError):
            return None
    return None


def get_public_group_id() -> str | None:
    value = get_server_setting(PUBLIC_GROUP_ID_SETTING, default=None)
    return _parse_uuid_setting_value(value)


def set_public_group_id(group_id: str) -> None:
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group_id),
        description="UUID of the server-wide Public LibraryGroup (default/fallback access scope).",
    )


def get_public_group() -> LibraryGroup:
    """
    Return the server-wide Public LibraryGroup (default/fallback access scope).

    Public is identified by the ServerSetting `public_group_id` rather than a
    slug or display name. If missing or invalid, this function repairs the
    setting and/or creates the default public group.
    """
    public_id = get_public_group_id()
    if public_id is not None:
        try:
            group = LibraryGroup.objects.get(pk=public_id)
        except LibraryGroup.DoesNotExist:
            group = None

        if group is not None:
            return group

    # Repair path for existing installs: prefer the legacy display name before
    # the new default display name. Identity remains the setting value.
    existing = (
        LibraryGroup.objects.filter(name__in=["Public", DEFAULT_PUBLIC_GROUP_NAME])
        .order_by("created_at", "id")
        .first()
    )
    if existing is not None:
        set_public_group_id(str(existing.id))
        return existing

    group = LibraryGroup.objects.create(
        name=DEFAULT_PUBLIC_GROUP_NAME,
        description=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    )
    set_public_group_id(str(group.id))
    return group


def configure_public_group(*, name: str, description: str = "") -> LibraryGroup:
    normalized_name = str(name or "").strip()
    normalized_description = str(description or "").strip()
    if not normalized_name:
        raise ValidationError({"public_group_name": "Public group name is required."})

    group = get_public_group()
    group.name = normalized_name
    group.description = normalized_description
    group.full_clean()
    group.save(update_fields=["name", "description", "updated_at"])
    return group


def ensure_user_public_membership(*, user) -> LibraryGroupMembership:
    """
    Ensure the user has a Public membership.

    Public is the default/fallback group for new users, but it is not mandatory
    if the user belongs to at least one other group.
    """
    public = get_public_group()
    membership, _created = LibraryGroupMembership.objects.get_or_create(
        user=user,
        group=public,
        defaults={"is_curator": False},
    )
    if membership.is_curator:
        membership.is_curator = False
        membership.full_clean()
        membership.save(update_fields=["is_curator", "updated_at"])
    return membership


def ensure_user_has_at_least_one_group(*, user) -> None:
    """
    Invariant: every user must have at least one LibraryGroupMembership.

    If the user has no memberships, add a Public reader membership as a fallback.
    """
    if LibraryGroupMembership.objects.filter(user=user).exists():
        return
    ensure_user_public_membership(user=user)


def ensure_book_public_assignment(*, book: Book, added_by=None) -> BookGroupAssignment:
    public = get_public_group()
    assignment, _created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=public,
        defaults={"added_by": added_by},
    )
    return assignment


def ensure_book_has_at_least_one_group(*, book: Book, added_by=None) -> None:
    if BookGroupAssignment.objects.filter(book=book).exists():
        return
    ensure_book_public_assignment(book=book, added_by=added_by)


def bootstrap_public_group_membership_and_assignments() -> None:
    """
    Best-effort bootstrap for existing installs:
    - Ensure Public group exists
    - Ensure every user has at least one group (Public fallback if needed)
    - Ensure every book has at least one group (Public fallback if needed)
    """
    User = get_user_model()
    with transaction.atomic():
        for user in User.objects.all():
            ensure_user_has_at_least_one_group(user=user)
        for book in Book.objects.all():
            ensure_book_has_at_least_one_group(book=book, added_by=None)


def add_book_to_group(*, actor, book: Book, group: LibraryGroup) -> BookGroupAssignment:
    """
    Safe path for adding a book to a LibraryGroup.

    Permission model:
    - Owner/Manager/Librarian may add any book to any group.
    - Curator may add a book only to their non-Public group, and only if they can already view the book.
    """
    if policies.can_manage_library(actor):
        assignment, _created = BookGroupAssignment.objects.get_or_create(
            book=book,
            group=group,
            defaults={"added_by": actor},
        )
        return assignment

    if is_public_group(group):
        raise PermissionDenied("Curators cannot add books to Public.")

    if not policies.can_curate_group(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    if not policies.can_view_book(user=actor, book=book):
        raise PermissionDenied("Curators can only add books they can already view.")

    assignment, _created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": actor},
    )
    return assignment


def remove_book_from_group(*, actor, book: Book, group: LibraryGroup) -> bool:
    """
    Safe path for removing a book from a LibraryGroup.

    Returns True if an assignment was removed, False if it did not exist.

    Invariant:
    - A book should not remain without any group assignments; if the last assignment is removed,
      the book is safely reassigned to Public.

    Permission model:
    - Owner/Manager/Librarian may remove from any group.
    - Curator may remove only from their non-Public group.
    """
    if not policies.can_manage_library(actor):
        if is_public_group(group):
            raise PermissionDenied("Curators cannot remove books from Public.")
        if not policies.can_curate_group(user=actor, group=group):
            raise PermissionDenied("Not allowed.")

    with transaction.atomic():
        qs = BookGroupAssignment.objects.filter(book=book, group=group)
        existed = qs.exists()
        if existed:
            qs.delete()
            # Shelf invariant: a group-owned shelf may contain only books assigned to that group.
            # When a book is removed from a group, remove it from shelves owned by that group.
            from shelves.models import Shelf, ShelfItem

            ShelfItem.objects.filter(
                shelf__owner_type=Shelf.OWNER_TYPE_GROUP,
                shelf__owner_group=group,
                book=book,
            ).delete()
        ensure_book_has_at_least_one_group(book=book, added_by=actor)
    return existed


def add_user_to_group(
    *,
    actor,
    target_user,
    group: LibraryGroup,
    is_curator: bool = False,
) -> LibraryGroupMembership:
    """
    Safe path for adding (or updating) a user's membership in a LibraryGroup.

    Rules:
    - Only Owner/Manager may manage memberships.
    - Public cannot have Curators.
    - Idempotent: existing membership is updated to the requested curator status.
    """
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    is_curator = bool(is_curator)
    if is_curator and is_public_group(group):
        raise ValidationError({"is_curator": "Public group cannot have curators."})

    membership, created = LibraryGroupMembership.objects.get_or_create(
        user=target_user,
        group=group,
        defaults={"is_curator": is_curator},
    )
    if not created and membership.is_curator != is_curator:
        membership.is_curator = is_curator
        membership.full_clean()
        membership.save(update_fields=["is_curator", "updated_at"])
    return membership


def update_user_group_membership(
    *,
    actor,
    membership: LibraryGroupMembership,
    is_curator: bool,
) -> LibraryGroupMembership:
    """
    Safe path for updating an existing membership's curator status.
    """
    group = membership.group
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    is_curator = bool(is_curator)
    if is_curator and is_public_group(group):
        raise ValidationError({"is_curator": "Public group cannot have curators."})

    if membership.is_curator != is_curator:
        membership.is_curator = is_curator
        membership.full_clean()
        membership.save(update_fields=["is_curator", "updated_at"])
    return membership


def remove_user_from_group(
    *,
    actor,
    membership: LibraryGroupMembership,
) -> None:
    """
    Safe path for removing a user's membership in a LibraryGroup.

    Rules:
    - Only Owner/Manager may manage memberships.
    - Users must always have at least one membership. Removing the final membership
      succeeds, and Public is re-added as a fallback.
    """
    group = membership.group
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    target_user = membership.user
    with transaction.atomic():
        membership.delete()
        ensure_user_has_at_least_one_group(user=target_user)


@transaction.atomic
def delete_library_group(*, actor, group: LibraryGroup) -> dict[str, int]:
    """
    Destructively delete a non-Public LibraryGroup.

    Behavior:
    - Removes all book assignments for the group.
    - Removes all user memberships for the group.
    - Deletes group-owned shelves and shelf items.
    - Deletes the group.
    - Reconciles affected books/users back to Public if they would otherwise have
      zero groups/memberships.

    Returns counts for diagnostics.
    """
    if is_public_group(group):
        raise ValidationError("Public group cannot be deleted.")
    if not policies.can_delete_library_group(actor, group=group):
        raise PermissionDenied("Not allowed.")

    group_id = group.id

    affected_book_ids = list(
        BookGroupAssignment.objects.filter(group=group).values_list("book_id", flat=True)
    )
    affected_user_ids = list(
        LibraryGroupMembership.objects.filter(group=group).values_list("user_id", flat=True)
    )

    removed_assignments = BookGroupAssignment.objects.filter(group=group).count()
    removed_memberships = LibraryGroupMembership.objects.filter(group=group).count()

    # Delete group-owned shelves and items explicitly (do not rely on FK cascade).
    from shelves.models import Shelf, ShelfItem

    shelf_qs = Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group=group)
    shelf_ids = list(shelf_qs.values_list("id", flat=True))
    deleted_shelf_items = ShelfItem.objects.filter(shelf_id__in=shelf_ids).count() if shelf_ids else 0
    if shelf_ids:
        ShelfItem.objects.filter(shelf_id__in=shelf_ids).delete()
    deleted_shelves = len(shelf_ids)
    if shelf_ids:
        shelf_qs.delete()

    # Remove group relationships.
    BookGroupAssignment.objects.filter(group_id=group_id).delete()
    LibraryGroupMembership.objects.filter(group_id=group_id).delete()

    # Delete the group itself.
    group.delete()

    # Reconcile: any affected books/users left with zero groups/memberships fall back to Public.
    for book_id in affected_book_ids:
        if not BookGroupAssignment.objects.filter(book_id=book_id).exists():
            try:
                book = Book.objects.get(pk=book_id)
            except Book.DoesNotExist:
                continue
            ensure_book_public_assignment(book=book, added_by=actor)

    User = get_user_model()
    for user_id in affected_user_ids:
        if not LibraryGroupMembership.objects.filter(user_id=user_id).exists():
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                continue
            ensure_user_public_membership(user=user)

    return {
        "removed_book_assignments": int(removed_assignments),
        "removed_memberships": int(removed_memberships),
        "deleted_shelves": int(deleted_shelves),
        "deleted_shelf_items": int(deleted_shelf_items),
    }
