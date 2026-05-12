from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from core import policies
from core.server_settings import get_server_setting, set_server_setting
from .models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership, is_public_group

PUBLIC_GROUP_ID_SETTING = "public_group_id"


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

    Public is identified by the ServerSetting `public_group_id` rather than a slug.
    If missing or invalid, this function repairs the setting and/or creates a Public group.
    """
    public_id = get_public_group_id()
    if public_id is not None:
        try:
            group = LibraryGroup.objects.get(pk=public_id)
        except LibraryGroup.DoesNotExist:
            group = None

        if group is not None:
            if group.name != "Public":
                group.name = "Public"
                group.save(update_fields=["name", "updated_at"])
            return group

    # Repair path: prefer an existing group named exactly "Public".
    existing = LibraryGroup.objects.filter(name="Public").order_by("created_at", "id").first()
    if existing is not None:
        set_public_group_id(str(existing.id))
        return existing

    group = LibraryGroup.objects.create(name="Public", description="Default shared library group.")
    set_public_group_id(str(group.id))
    return group


def ensure_user_public_membership(*, user) -> LibraryGroupMembership:
    """
    Ensure the user has a Public membership (reader role).

    Public is the default/fallback group for new users, but it is not mandatory
    if the user belongs to at least one other group.
    """
    public = get_public_group()
    membership, _created = LibraryGroupMembership.objects.get_or_create(
        user=user,
        group=public,
        defaults={"role": LibraryGroupMembership.ROLE_READER},
    )
    if membership.role != LibraryGroupMembership.ROLE_READER:
        membership.role = LibraryGroupMembership.ROLE_READER
        membership.save(update_fields=["role", "updated_at"])
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
    role: str = LibraryGroupMembership.ROLE_READER,
) -> LibraryGroupMembership:
    """
    Safe path for adding (or updating) a user's membership in a LibraryGroup.

    Rules:
    - Only Owner/Manager may manage memberships.
    - Public cannot have Curators and role is forced to reader.
    - Non-Public: role must be reader or curator.
    - Idempotent: existing membership is updated to the requested role (subject to rules).
    """
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    if is_public_group(group):
        if role != LibraryGroupMembership.ROLE_READER:
            raise ValidationError({"role": "Public group cannot have curators."})
        role = LibraryGroupMembership.ROLE_READER
    else:
        if role not in {LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR}:
            raise ValidationError({"role": "Invalid membership role."})

    membership, created = LibraryGroupMembership.objects.get_or_create(
        user=target_user,
        group=group,
        defaults={"role": role},
    )
    if not created and membership.role != role:
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
    return membership


def update_user_group_membership(
    *,
    actor,
    membership: LibraryGroupMembership,
    role: str,
) -> LibraryGroupMembership:
    """
    Safe path for updating an existing membership's role.
    """
    group = membership.group
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")

    if is_public_group(group):
        if role != LibraryGroupMembership.ROLE_READER:
            raise ValidationError({"role": "Public group cannot have curators."})
        role = LibraryGroupMembership.ROLE_READER
    else:
        if role not in {LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR}:
            raise ValidationError({"role": "Invalid membership role."})

    if membership.role != role:
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
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
