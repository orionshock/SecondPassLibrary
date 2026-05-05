from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership


PUBLIC_GROUP_SLUG = "public"


def get_public_group() -> LibraryGroup:
    group, _created = LibraryGroup.objects.get_or_create(
        slug=PUBLIC_GROUP_SLUG,
        defaults={
            "name": "Public",
            "description": "Default shared library group.",
            "is_public": True,
            "is_system": True,
        },
    )
    # If an existing group uses the slug, ensure flags are consistent.
    updates = {}
    if not group.is_public:
        updates["is_public"] = True
    if not group.is_system:
        updates["is_system"] = True
    if group.name != "Public":
        updates["name"] = "Public"
    if updates:
        for k, v in updates.items():
            setattr(group, k, v)
        group.save(update_fields=[*updates.keys(), "updated_at"])
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

