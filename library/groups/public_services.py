from __future__ import annotations

from dataclasses import dataclass
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef

from core.models import ServerSetting
from core.operational_logging import info_on_commit, suppress_state_change_logging
from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    RECOVERED_PUBLIC_GROUP_DESCRIPTION,
    get_public_group,
    get_public_group_id,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache_on_commit


PUBLIC_GROUP_SETTING_DESCRIPTION = "Public/Common Room group id."
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicGroupRepairResult:
    group: LibraryGroup
    created_new_group: bool
    users_restored: int
    books_restored: int


def configure_public_group(*, name: str, description: str = "") -> LibraryGroup:
    with transaction.atomic():
        group = get_public_group()
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
        _lock_public_group_setting()
        selected = LibraryGroup.objects.select_for_update().get(pk=group.pk)
        if selected.memberships.filter(is_curator=True).exists():
            raise ValidationError(
                "Remove curator memberships before selecting this group as Public."
            )
        with suppress_state_change_logging():
            _store_public_group_id(selected)
        info_on_commit(
            logger,
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

            users_restored = _restore_orphan_users_to_public(public_group=group)
            books_restored = _restore_orphan_books_to_public(
                public_group=group,
                added_by=actor,
            )
            if users_restored or books_restored:
                invalidate_visible_books_cache_on_commit()

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


def _restore_orphan_users_to_public(*, public_group: LibraryGroup) -> int:
    user_ids = list(
        get_user_model()
        .objects.annotate(
            has_group=Exists(
                LibraryGroupMembership.objects.filter(user_id=OuterRef("pk"))
            )
        )
        .filter(has_group=False)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if not user_ids:
        return 0
    rows = [
        LibraryGroupMembership(
            user_id=user_id,
            group=public_group,
            is_curator=False,
        )
        for user_id in user_ids
    ]
    return len(LibraryGroupMembership.objects.bulk_create(rows))


def _restore_orphan_books_to_public(*, public_group: LibraryGroup, added_by=None) -> int:
    book_ids = list(
        Book.objects.annotate(
            has_group=Exists(
                BookGroupAssignment.objects.filter(book_id=OuterRef("pk"))
            )
        )
        .filter(has_group=False)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if not book_ids:
        return 0
    rows = [
        BookGroupAssignment(
            book_id=book_id,
            group=public_group,
            added_by=added_by,
        )
        for book_id in book_ids
    ]
    return len(BookGroupAssignment.objects.bulk_create(rows))


def _lock_public_group_setting() -> ServerSetting:
    setting, _created = ServerSetting.objects.get_or_create(
        key=PUBLIC_GROUP_ID_SETTING,
        defaults={
            "value": str(get_public_group_id() or ""),
            "description": PUBLIC_GROUP_SETTING_DESCRIPTION,
        },
    )
    return ServerSetting.objects.select_for_update().get(pk=setting.pk)


def _store_public_group_id(group: LibraryGroup) -> None:
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group.id),
        description=PUBLIC_GROUP_SETTING_DESCRIPTION,
    )


def _public_group_name(name: str | None) -> str:
    value = str(name or "").strip()
    return value or DEFAULT_PUBLIC_GROUP_NAME


def _public_group_description(description: str | None) -> str:
    return str(description or "").strip()
