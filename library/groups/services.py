from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction

from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    get_public_group,
)
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership


def configure_public_group(*, name: str, description: str = ""):
    group = LibraryGroup.objects.create(
        name=name or DEFAULT_PUBLIC_GROUP_NAME,
        description=description or DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    )
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group.id),
        description="LibraryReWrite2607 Public/Common Room group id.",
    )
    return group


def ensure_user_public_membership(*, user):
    group = _get_or_create_public_group()
    membership, _created = LibraryGroupMembership.objects.get_or_create(user=user, group=group)
    return membership


def ensure_user_has_at_least_one_group(*, user) -> None:
    if not LibraryGroupMembership.objects.filter(user=user).exists():
        ensure_user_public_membership(user=user)


def ensure_book_public_assignment(*, book, added_by=None):
    group = _get_or_create_public_group()
    assignment, _created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": added_by},
    )
    return assignment


def ensure_book_has_at_least_one_group(*, book, added_by=None) -> None:
    if not BookGroupAssignment.objects.filter(book=book).exists():
        ensure_book_public_assignment(book=book, added_by=added_by)


def bootstrap_public_group_membership_and_assignments() -> None:
    _get_or_create_public_group()


def add_book_to_group(*, actor, book, group):
    if group is None:
        raise PermissionDenied("Missing group.")
    assignment, _created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": actor},
    )
    return assignment


def remove_book_from_group(*, actor, book, group) -> bool:
    deleted, _ = BookGroupAssignment.objects.filter(book=book, group=group).delete()
    return bool(deleted)


def _get_or_create_public_group() -> LibraryGroup:
    try:
        return get_public_group()
    except LibraryGroup.DoesNotExist:
        pass

    with transaction.atomic():
        group = LibraryGroup.objects.create(
            name=DEFAULT_PUBLIC_GROUP_NAME,
            description=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
        )
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(group.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )
    return group
