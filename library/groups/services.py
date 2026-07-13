from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import (
    info_on_commit,
    user_uuid,
)
from library.groups.book_assignments import restore_selected_books_without_groups
from library.groups.memberships import restore_selected_users_without_groups
from library.groups.public_group import (
    get_public_group,
    is_public_group,
)
from library.models import LibraryGroup
from library.queries import invalidate_visible_books_cache_on_commit


logger = logging.getLogger(__name__)


def create_library_group(*, name: str, description: str = "") -> LibraryGroup:
    group = LibraryGroup.objects.create(name=_required_name(name), description=description or "")
    info_on_commit(logger, "Library group created: group=%s", group.pk)
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
        info_on_commit(
            logger,
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
        public_group = get_public_group() if user_ids or book_ids else None
        users_restored = restore_selected_users_without_groups(
            user_ids, public_group=public_group
        )
        books_restored = restore_selected_books_without_groups(
            book_ids, added_by=actor, public_group=public_group
        )
        if deleted_count:
            invalidate_visible_books_cache_on_commit()
    if deleted_count:
        info_on_commit(
            logger,
            "Library group deleted: actor=%s group=%s fallback_to_public=%s "
            "users_restored=%d books_restored=%d",
            user_uuid(actor),
            group_id,
            bool(users_restored or books_restored),
            users_restored,
            books_restored,
        )
    return bool(deleted_count)

def _required_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        raise ValidationError("Group name is required.")
    return value
