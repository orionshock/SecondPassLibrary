from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import info_on_commit, safe_log_label, user_log_label
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache_on_commit


logger = logging.getLogger(__name__)


def add_user_to_group(
    *, user, group: LibraryGroup, is_curator: bool = False, actor=None
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
            group_id, group_name, target_name, actor_name = _membership_log_values(
                group=group,
                user=user,
                actor=actor,
            )
            info_on_commit(
                logger,
                "Library group membership curator changed: group_name=%s group=%s "
                "target=%s actor=%s curator=%s",
                group_name,
                group_id,
                target_name,
                actor_name,
                True,
            )
        if created:
            invalidate_visible_books_cache_on_commit()
            group_id, group_name, target_name, actor_name = _membership_log_values(
                group=group,
                user=user,
                actor=actor,
            )
            info_on_commit(
                logger,
                "Library group membership added: group_name=%s group=%s target=%s "
                "actor=%s curator=%s",
                group_name,
                group_id,
                target_name,
                actor_name,
                bool(membership.is_curator),
            )
        return membership


def set_group_membership_curator(
    *, membership: LibraryGroupMembership, is_curator: bool, actor=None
) -> LibraryGroupMembership:
    with transaction.atomic():
        _lock_user_for_group_mutation(membership.user)
        value = bool(is_curator)
        if membership.is_curator != value:
            membership.is_curator = value
            membership.save(update_fields=["is_curator", "updated_at"])
            group_id, group_name, target_name, actor_name = _membership_log_values(
                group=membership.group,
                user=membership.user,
                actor=actor,
            )
            info_on_commit(
                logger,
                "Library group membership curator changed: group_name=%s group=%s "
                "target=%s actor=%s curator=%s",
                group_name,
                group_id,
                target_name,
                actor_name,
                value,
            )
        return membership


def remove_user_from_group(*, user, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        user = _lock_user_for_group_mutation(user)
        group_id, group_name, target_name, actor_name = _membership_log_values(
            group=group,
            user=user,
            actor=actor,
        )
        was_curator = bool(
            LibraryGroupMembership.objects.filter(user=user, group=group)
            .values_list("is_curator", flat=True)
            .first()
        )
        deleted, _ = LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        restored = _ensure_user_has_at_least_one_group_locked(user=user)
        if deleted and not restored:
            invalidate_visible_books_cache_on_commit()
    if deleted:
        info_on_commit(
            logger,
            "Library group membership removed: group_name=%s group=%s target=%s "
            "actor=%s curator=%s fallback_to_public=%s",
            group_name,
            group_id,
            target_name,
            actor_name,
            was_curator,
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
        invalidate_visible_books_cache_on_commit()
    return membership


def _ensure_user_has_at_least_one_group_locked(
    *, user, public_group: LibraryGroup | None = None
) -> bool:
    if not LibraryGroupMembership.objects.filter(user=user).exists():
        _ensure_user_public_membership_locked(user=user, public_group=public_group)
        return True
    return False


def restore_selected_users_without_groups(
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


def _membership_log_values(*, group, user, actor) -> tuple[str, str, str, str]:
    group_id = str(group.pk)
    return (
        group_id,
        safe_log_label(group.name, fallback=group_id),
        user_log_label(user),
        user_log_label(actor),
    )
