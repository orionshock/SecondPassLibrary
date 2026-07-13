from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import info_on_commit, user_uuid
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache


logger = logging.getLogger(__name__)


def add_user_to_group(
    *, user, group: LibraryGroup, is_curator: bool = False
) -> LibraryGroupMembership:
    if group is None:
        raise ValidationError("Group is required.")
    with transaction.atomic():
        user = _lock_user_for_group_mutation(user)
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
    with transaction.atomic():
        _lock_user_for_group_mutation(membership.user)
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
        user = _lock_user_for_group_mutation(user)
        deleted, _ = LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        restored = _ensure_user_has_at_least_one_group_locked(user=user)
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
    with transaction.atomic():
        user = _lock_user_for_group_mutation(user)
        return _ensure_user_public_membership_locked(user=user, public_group=public_group)


def ensure_user_has_at_least_one_group(
    *, user, public_group: LibraryGroup | None = None
) -> bool:
    with transaction.atomic():
        user = _lock_user_for_group_mutation(user)
        return _ensure_user_has_at_least_one_group_locked(
            user=user,
            public_group=public_group,
        )


def _ensure_user_public_membership_locked(
    *, user, public_group: LibraryGroup | None = None
) -> LibraryGroupMembership:
    group = public_group or get_public_group()
    membership, created = LibraryGroupMembership.objects.get_or_create(user=user, group=group)
    if created:
        _invalidate_visible_books_cache_on_commit()
    return membership


def _ensure_user_has_at_least_one_group_locked(
    *, user, public_group: LibraryGroup | None = None
) -> bool:
    if not LibraryGroupMembership.objects.filter(user=user).exists():
        _ensure_user_public_membership_locked(user=user, public_group=public_group)
        return True
    return False


def _restore_users_without_groups(
    user_ids: list, *, public_group: LibraryGroup | None = None
) -> int:
    restored = 0
    locked_user_ids = list(
        get_user_model()
        .objects.select_for_update()
        .filter(pk__in=user_ids)
        .values_list("pk", flat=True)
    )
    for user_id in locked_user_ids:
        if not LibraryGroupMembership.objects.filter(user_id=user_id).exists():
            group = public_group or get_public_group()
            LibraryGroupMembership.objects.get_or_create(user_id=user_id, group=group)
            restored += 1
    return restored


def _lock_user_for_group_mutation(user):
    return get_user_model().objects.select_for_update().get(pk=user.pk)


def _invalidate_visible_books_cache_on_commit() -> None:
    transaction.on_commit(invalidate_visible_books_cache)


def _log_info(message: str, *args) -> None:
    info_on_commit(logger, message, *args)
