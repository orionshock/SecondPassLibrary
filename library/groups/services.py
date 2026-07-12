from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
    get_public_group,
    is_public_group,
)
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache
from shelves.library_hooks import remove_book_from_group_owned_shelves


PUBLIC_GROUP_SETTING_DESCRIPTION = "Public/Common Room group id."


def create_library_group(*, name: str, description: str = "") -> LibraryGroup:
    return LibraryGroup.objects.create(name=_required_name(name), description=description or "")


def update_library_group(
    *, group: LibraryGroup, name: str | None = None, description: str | None = None
) -> LibraryGroup:
    update_fields: list[str] = []
    if name is not None:
        group.name = _required_name(name)
        update_fields.append("name")
    if description is not None:
        group.description = description
        update_fields.append("description")
    if update_fields:
        group.save(update_fields=[*update_fields, "updated_at"])
    return group


def delete_library_group(*, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        if is_public_group(group):
            raise ValidationError("Public/Common Room group cannot be deleted.")
        user_ids = list(group.memberships.values_list("user_id", flat=True))
        book_ids = list(group.book_assignments.values_list("book_id", flat=True))
        deleted_count, _ = group.delete()
        public_group = _get_or_create_public_group() if user_ids or book_ids else None
        _restore_users_without_groups(user_ids, public_group=public_group)
        _restore_books_without_groups(
            book_ids, added_by=actor, public_group=public_group
        )
        if deleted_count:
            _invalidate_visible_books_cache_on_commit()
    return bool(deleted_count)


def configure_public_group(*, name: str, description: str = "") -> LibraryGroup:
    with transaction.atomic():
        group = _get_or_create_public_group()
        group.name = name or DEFAULT_PUBLIC_GROUP_NAME
        group.description = description or DEFAULT_PUBLIC_GROUP_DESCRIPTION
        group.save(update_fields=["name", "description", "updated_at"])
        _store_public_group_id(group)
        return group


def set_public_group_identity(*, group: LibraryGroup) -> LibraryGroup:
    with transaction.atomic():
        selected = LibraryGroup.objects.select_for_update().get(pk=group.pk)
        if selected.memberships.filter(is_curator=True).exists():
            raise ValidationError(
                "Remove curator memberships before selecting this group as Public."
            )
        _store_public_group_id(selected)
        return selected


def create_fresh_public_group() -> LibraryGroup:
    with transaction.atomic():
        group = LibraryGroup.objects.create(
            name=DEFAULT_PUBLIC_GROUP_NAME,
            description=RECOVERED_PUBLIC_GROUP_DESCRIPTION,
        )
        _store_public_group_id(group)
        return group


def add_user_to_group(*, user, group: LibraryGroup, is_curator: bool = False) -> LibraryGroupMembership:
    if group is None:
        raise ValidationError("Group is required.")
    with transaction.atomic():
        membership, created = LibraryGroupMembership.objects.get_or_create(
            user=user,
            group=group,
            defaults={"is_curator": bool(is_curator)},
        )
        if not created and is_curator and not membership.is_curator:
            membership.is_curator = True
            membership.save(update_fields=["is_curator", "updated_at"])
        if created:
            _invalidate_visible_books_cache_on_commit()
        return membership


def set_group_membership_curator(
    *, membership: LibraryGroupMembership, is_curator: bool
) -> LibraryGroupMembership:
    membership.is_curator = bool(is_curator)
    membership.save(update_fields=["is_curator", "updated_at"])
    return membership


def remove_user_from_group(*, user, group: LibraryGroup) -> bool:
    with transaction.atomic():
        deleted, _ = LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        restored = ensure_user_has_at_least_one_group(user=user)
        if deleted and not restored:
            _invalidate_visible_books_cache_on_commit()
    return bool(deleted)


def ensure_user_public_membership(
    *, user, public_group: LibraryGroup | None = None
) -> LibraryGroupMembership:
    group = public_group or _get_or_create_public_group()
    membership, created = LibraryGroupMembership.objects.get_or_create(user=user, group=group)
    if created:
        _invalidate_visible_books_cache_on_commit()
    return membership


def ensure_user_has_at_least_one_group(
    *, user, public_group: LibraryGroup | None = None
) -> bool:
    if not LibraryGroupMembership.objects.filter(user=user).exists():
        ensure_user_public_membership(user=user, public_group=public_group)
        return True
    return False


def add_book_to_group(
    *, book, group: LibraryGroup, actor=None, added_by=None
) -> BookGroupAssignment:
    if group is None:
        raise ValidationError("Group is required.")
    creator = added_by if added_by is not None else actor
    return _create_book_assignment(book=book, group=group, added_by=creator)


def remove_book_from_group(*, book, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        if BookGroupAssignment.objects.filter(book=book, group=group).exists():
            remove_book_from_group_owned_shelves(book=book, group=group)
        deleted, _ = BookGroupAssignment.objects.filter(book=book, group=group).delete()
        restored = ensure_book_has_at_least_one_group(book=book, added_by=actor)
        if deleted and not restored:
            _invalidate_visible_books_cache_on_commit()
    return bool(deleted)


def ensure_book_public_assignment(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> BookGroupAssignment:
    group = public_group or _get_or_create_public_group()
    return _create_book_assignment(book=book, group=group, added_by=added_by)


def ensure_book_has_at_least_one_group(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> bool:
    if not BookGroupAssignment.objects.filter(book=book).exists():
        ensure_book_public_assignment(
            book=book, added_by=added_by, public_group=public_group
        )
        return True
    return False


def bootstrap_public_group_membership_and_assignments() -> None:
    _get_or_create_public_group()


def _restore_users_without_groups(
    user_ids: list, *, public_group: LibraryGroup | None = None
) -> None:
    for user_id in user_ids:
        if not LibraryGroupMembership.objects.filter(user_id=user_id).exists():
            group = public_group or _get_or_create_public_group()
            LibraryGroupMembership.objects.get_or_create(user_id=user_id, group=group)


def _restore_books_without_groups(
    book_ids: list, *, added_by=None, public_group: LibraryGroup | None = None
) -> None:
    for book_id in book_ids:
        if not BookGroupAssignment.objects.filter(book_id=book_id).exists():
            group = public_group or _get_or_create_public_group()
            BookGroupAssignment.objects.get_or_create(
                book_id=book_id,
                group=group,
                defaults={"added_by": added_by},
            )


def _create_book_assignment(*, book, group: LibraryGroup, added_by=None) -> BookGroupAssignment:
    assignment, created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": added_by},
    )
    if created:
        _invalidate_visible_books_cache_on_commit()
    return assignment


def _invalidate_visible_books_cache_on_commit() -> None:
    transaction.on_commit(invalidate_visible_books_cache)


def _get_or_create_public_group() -> LibraryGroup:
    return get_public_group()


def _store_public_group_id(group: LibraryGroup) -> None:
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group.id),
        description=PUBLIC_GROUP_SETTING_DESCRIPTION,
    )


def _required_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        raise ValidationError("Group name is required.")
    return value
