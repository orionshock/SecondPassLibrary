from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from core import policies
from .models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from .models import PUBLIC_GROUP_SLUG, is_public_group


def get_public_group() -> LibraryGroup:
    group, _created = LibraryGroup.objects.get_or_create(
        slug=PUBLIC_GROUP_SLUG,
        defaults={
            "name": "Public",
            "description": "Default shared library group.",
            "discoverability": LibraryGroup.DISCOVERABILITY_LISTED,
        },
    )
    # If an existing group uses the slug, ensure fields are consistent.
    updates = {}
    if group.discoverability != LibraryGroup.DISCOVERABILITY_LISTED:
        updates["discoverability"] = LibraryGroup.DISCOVERABILITY_LISTED
    if group.name != "Public":
        updates["name"] = "Public"
    if updates:
        for k, v in updates.items():
            setattr(group, k, v)
        group.save(update_fields=[*updates.keys(), "updated_at"])
    if not is_public_group(group):
        raise ValueError("Public group must have slug 'public'.")
    return group


def ensure_user_public_membership(*, user) -> LibraryGroupMembership:
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
    - Ensure every user is a member of Public
    - Ensure every book is assigned to Public
    """
    User = get_user_model()
    public = get_public_group()
    with transaction.atomic():
        for user in User.objects.all():
            LibraryGroupMembership.objects.get_or_create(
                user=user,
                group=public,
                defaults={"role": LibraryGroupMembership.ROLE_READER},
            )
        for book in Book.objects.all():
            BookGroupAssignment.objects.get_or_create(book=book, group=public)


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
    - Public membership cannot be removed; Public cannot have Curators and role is forced to reader.
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
    - Public membership is protected (cannot be removed).
    """
    group = membership.group
    if not policies.can_manage_group_membership(user=actor, group=group):
        raise PermissionDenied("Not allowed.")
    if is_public_group(group):
        raise PermissionDenied("Public membership cannot be removed.")
    membership.delete()
