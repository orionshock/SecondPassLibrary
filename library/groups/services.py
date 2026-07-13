from __future__ import annotations

from dataclasses import dataclass
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import (
    info_on_commit,
    suppress_state_change_logging,
    user_uuid,
)
from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
    get_public_group,
    get_public_group_id,
    is_public_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache
from shelves.library_hooks import remove_book_from_group_owned_shelves


PUBLIC_GROUP_SETTING_DESCRIPTION = "Public/Common Room group id."
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicGroupRepairResult:
    group: LibraryGroup
    created_new_group: bool
    users_restored: int
    books_restored: int


def create_library_group(*, name: str, description: str = "") -> LibraryGroup:
    group = LibraryGroup.objects.create(name=_required_name(name), description=description or "")
    _log_info("Library group created: group=%s", group.pk)
    return group


def update_library_group(
    *, group: LibraryGroup, name: str | None = None, description: str | None = None
) -> LibraryGroup:
    update_fields: list[str] = []
    if name is not None:
        value = _required_name(name)
        if group.name != value:
            group.name = value
            update_fields.append("name")
    if description is not None:
        value = description or ""
        if group.description != value:
            group.description = value
            update_fields.append("description")
    if update_fields:
        group.save(update_fields=[*update_fields, "updated_at"])
        _log_info(
            "Library group presentation changed: group=%s changed_fields=%s",
            group.pk,
            ",".join(sorted(update_fields)),
        )
    return group


def delete_library_group(*, group: LibraryGroup, actor=None) -> bool:
    group_id = group.pk
    with transaction.atomic():
        if is_public_group(group):
            raise ValidationError("Public/Common Room group cannot be deleted.")
        user_ids = list(group.memberships.values_list("user_id", flat=True))
        book_ids = list(group.book_assignments.values_list("book_id", flat=True))
        deleted_count, _ = group.delete()
        public_group = _get_or_create_public_group() if user_ids or book_ids else None
        users_restored = _restore_users_without_groups(user_ids, public_group=public_group)
        books_restored = _restore_books_without_groups(
            book_ids, added_by=actor, public_group=public_group
        )
        if deleted_count:
            _invalidate_visible_books_cache_on_commit()
    if deleted_count:
        _log_info(
            "Library group deleted: actor=%s group=%s fallback_to_public=%s "
            "users_restored=%d books_restored=%d",
            user_uuid(actor),
            group_id,
            bool(users_restored or books_restored),
            users_restored,
            books_restored,
        )
    return bool(deleted_count)


def configure_public_group(*, name: str, description: str = "") -> LibraryGroup:
    with transaction.atomic():
        group = _get_or_create_public_group()
        normalized_name = _public_group_name(name)
        normalized_description = _public_group_description(description)
        update_fields: list[str] = []
        if group.name != normalized_name:
            group.name = normalized_name
            update_fields.append("name")
        if group.description != normalized_description:
            group.description = normalized_description
            update_fields.append("description")
        if update_fields:
            group.save(update_fields=[*update_fields, "updated_at"])
        if str(get_public_group_id()) != str(group.id):
            _store_public_group_id(group)
        return group


def set_public_group_identity(*, group: LibraryGroup) -> LibraryGroup:
    with transaction.atomic():
        selected = LibraryGroup.objects.select_for_update().get(pk=group.pk)
        if selected.memberships.filter(is_curator=True).exists():
            raise ValidationError(
                "Remove curator memberships before selecting this group as Public."
            )
        with suppress_state_change_logging():
            _store_public_group_id(selected)
        _log_info(
            "Public/Common Room identity reassigned: group=%s reassigned=%s",
            selected.pk,
            True,
        )
        return selected


def create_fresh_public_group() -> LibraryGroup:
    with transaction.atomic():
        group = LibraryGroup.objects.create(
            name=DEFAULT_PUBLIC_GROUP_NAME,
            description=RECOVERED_PUBLIC_GROUP_DESCRIPTION,
        )
        _store_public_group_id(group)
        return group


def repair_public_group_identity(
    *, create_new_common_room: bool, actor=None
) -> PublicGroupRepairResult:
    with suppress_state_change_logging():
        with transaction.atomic():
            configured_id = get_public_group_id()
            configured_exists = bool(
                configured_id
                and LibraryGroup.objects.filter(pk=configured_id).exists()
            )
            if create_new_common_room:
                group = create_fresh_public_group()
            else:
                group = get_public_group()

            users_restored = 0
            for user in get_user_model().objects.order_by("pk").iterator():
                users_restored += ensure_user_has_at_least_one_group(
                    user=user,
                    public_group=group,
                )

            books_restored = 0
            for book in Book.objects.order_by("pk").iterator():
                books_restored += ensure_book_has_at_least_one_group(
                    book=book,
                    added_by=actor,
                    public_group=group,
                )

            result = PublicGroupRepairResult(
                group=group,
                created_new_group=create_new_common_room or not configured_exists,
                users_restored=users_restored,
                books_restored=books_restored,
            )

    info_on_commit(
        logger,
        "Public/Common Room identity repaired: group=%s created_new=%s "
        "users_restored=%d books_restored=%d",
        result.group.pk,
        result.created_new_group,
        result.users_restored,
        result.books_restored,
    )
    return result


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
            _log_info(
                "Library group membership curator changed: group=%s user=%s curator=%s",
                group.pk,
                user_uuid(user),
                True,
            )
        if created:
            _invalidate_visible_books_cache_on_commit()
            _log_info(
                "Library group membership added: group=%s user=%s curator=%s",
                group.pk,
                user_uuid(user),
                bool(membership.is_curator),
            )
        return membership


def set_group_membership_curator(
    *, membership: LibraryGroupMembership, is_curator: bool
) -> LibraryGroupMembership:
    value = bool(is_curator)
    if membership.is_curator != value:
        membership.is_curator = value
        membership.save(update_fields=["is_curator", "updated_at"])
        _log_info(
            "Library group membership curator changed: group=%s user=%s curator=%s",
            membership.group_id,
            user_uuid(membership.user),
            value,
        )
    return membership


def remove_user_from_group(*, user, group: LibraryGroup) -> bool:
    with transaction.atomic():
        deleted, _ = LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        restored = ensure_user_has_at_least_one_group(user=user)
        if deleted and not restored:
            _invalidate_visible_books_cache_on_commit()
    if deleted:
        _log_info(
            "Library group membership removed: group=%s user=%s fallback_to_public=%s",
            group.pk,
            user_uuid(user),
            bool(restored),
        )
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
    assignment, created = _create_book_assignment(
        book=book,
        group=group,
        added_by=creator,
    )
    if created:
        _log_info(
            "Book assigned to library group: actor=%s added_by=%s book=%s group=%s",
            user_uuid(actor),
            user_uuid(creator),
            book.pk,
            group.pk,
        )
    return assignment


def remove_book_from_group(*, book, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        if BookGroupAssignment.objects.filter(book=book, group=group).exists():
            remove_book_from_group_owned_shelves(book=book, group=group)
        deleted, _ = BookGroupAssignment.objects.filter(book=book, group=group).delete()
        restored = ensure_book_has_at_least_one_group(book=book, added_by=actor)
        if deleted and not restored:
            _invalidate_visible_books_cache_on_commit()
    if deleted:
        _log_info(
            "Book removed from library group: actor=%s book=%s group=%s fallback_to_public=%s",
            user_uuid(actor),
            book.pk,
            group.pk,
            bool(restored),
        )
    return bool(deleted)


def ensure_book_public_assignment(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> BookGroupAssignment:
    group = public_group or _get_or_create_public_group()
    assignment, created = _create_book_assignment(book=book, group=group, added_by=added_by)
    if created:
        _log_info(
            "Book assigned to library group: actor=%s added_by=%s book=%s group=%s",
            "none",
            user_uuid(added_by),
            book.pk,
            group.pk,
        )
    return assignment


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
) -> int:
    restored = 0
    for user_id in user_ids:
        if not LibraryGroupMembership.objects.filter(user_id=user_id).exists():
            group = public_group or _get_or_create_public_group()
            LibraryGroupMembership.objects.get_or_create(user_id=user_id, group=group)
            restored += 1
    return restored


def _restore_books_without_groups(
    book_ids: list, *, added_by=None, public_group: LibraryGroup | None = None
) -> int:
    restored = 0
    for book_id in book_ids:
        if not BookGroupAssignment.objects.filter(book_id=book_id).exists():
            group = public_group or _get_or_create_public_group()
            BookGroupAssignment.objects.get_or_create(
                book_id=book_id,
                group=group,
                defaults={"added_by": added_by},
            )
            restored += 1
    return restored


def _create_book_assignment(
    *, book, group: LibraryGroup, added_by=None
) -> tuple[BookGroupAssignment, bool]:
    assignment, created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": added_by},
    )
    if created:
        _invalidate_visible_books_cache_on_commit()
    return assignment, created


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


def _public_group_name(name: str | None) -> str:
    value = str(name or "").strip()
    return value or DEFAULT_PUBLIC_GROUP_NAME


def _public_group_description(description: str | None) -> str:
    return str(description or "").strip()


def _log_info(message: str, *args) -> None:
    info_on_commit(logger, message, *args)
