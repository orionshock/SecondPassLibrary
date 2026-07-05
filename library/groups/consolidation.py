from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import logging
from typing import Any

from django.db import transaction

from core import server_settings
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf

from .public_group import get_public_group
from .services import delete_library_group, remove_book_from_group, remove_user_from_group
from .consolidation_types import (
    PHASES,
    AdvancedGroupsConsolidationError,
    AdvancedGroupsConsolidationNotNeeded,
    AdvancedGroupsDisablePlan,
    AdvancedGroupsDisableResult,
    AdvancedGroupsPlanStale,
    BookAssignmentRemovalPlan,
    BookPublicFallbackPlan,
    GroupDeletionPlan,
    MembershipRemovalPlan,
    ShelfMovePlan,
    UserPublicFallbackPlan,
)


logger = logging.getLogger(__name__)


def _display_group_name(group: LibraryGroup) -> str:
    name = str(group.name or "").strip()
    if name:
        return name
    return f"Unnamed group {str(group.id)[:8]}"


def _limited(values: tuple[Any, ...], display_limit: int | None) -> tuple[Any, ...]:
    if display_limit is None:
        return values
    return values[: max(0, int(display_limit))]


def _fingerprint_payload(plan: AdvancedGroupsDisablePlan) -> dict[str, Any]:
    return {
        "enabled_before": plan.enabled_before,
        "public_group_id": plan.public_group_id,
        "shelves": [vars(op) for op in plan.shelf_moves],
        "book_assignments": [vars(op) for op in plan.book_assignment_removals],
        "memberships": [vars(op) for op in plan.membership_removals],
        "groups": [vars(op) for op in plan.group_deletions],
    }


def _make_fingerprint(plan: AdvancedGroupsDisablePlan) -> str:
    data = json.dumps(_fingerprint_payload(plan), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_advanced_groups_disable_plan(
    display_limit: int | None = None,
) -> AdvancedGroupsDisablePlan:
    public = get_public_group()
    public_id = str(public.id)
    custom_groups = tuple(
        LibraryGroup.objects.exclude(id=public.id).order_by("name", "id")
    )
    group_ids = tuple(group.id for group in custom_groups)
    group_names = {str(group.id): _display_group_name(group) for group in custom_groups}

    public_shelf_names = set(
        Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group=public)
        .values_list("name", flat=True)
    )
    shelf_qs = (
        Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group_id__in=group_ids)
        .select_related("owner_group")
        .prefetch_related("items")
        .order_by("owner_group__name", "name", "id")
    )
    planned_names: dict[str, int] = {}
    shelf_moves: list[ShelfMovePlan] = []
    for shelf in shelf_qs:
        group_name = group_names[str(shelf.owner_group_id)]
        new_name = f"{group_name} / {shelf.name}"
        planned_names[new_name] = planned_names.get(new_name, 0) + 1
        shelf_moves.append(
            ShelfMovePlan(
                shelf_id=str(shelf.id),
                group_id=str(shelf.owner_group_id),
                group_name=group_name,
                old_name=shelf.name,
                new_name=new_name,
                item_count=shelf.items.count(),
                name_collision=new_name in public_shelf_names,
            )
        )
    shelf_moves = [
        replace(op, name_collision=op.name_collision or planned_names[op.new_name] > 1)
        for op in shelf_moves
    ]

    public_book_ids = set(
        BookGroupAssignment.objects.filter(group=public).values_list("book_id", flat=True)
    )
    assignments = (
        BookGroupAssignment.objects.filter(group_id__in=group_ids)
        .select_related("book", "group")
        .order_by("group__name", "book__title", "id")
    )
    book_groups: dict[str, set[str]] = {}
    book_titles: dict[str, str] = {}
    assignment_removals: list[BookAssignmentRemovalPlan] = []
    for assignment in assignments:
        book_id = str(assignment.book_id)
        group_name = group_names[str(assignment.group_id)]
        book_groups.setdefault(book_id, set()).add(group_name)
        book_titles[book_id] = assignment.book.title
        assignment_removals.append(
            BookAssignmentRemovalPlan(
                assignment_id=str(assignment.id),
                book_id=book_id,
                title=assignment.book.title,
                group_id=str(assignment.group_id),
                group_name=group_name,
                expects_public_fallback=assignment.book_id not in public_book_ids,
            )
        )
    book_fallbacks = tuple(
        BookPublicFallbackPlan(
            book_id=book_id,
            title=book_titles[book_id],
            removed_group_names=tuple(sorted(names)),
        )
        for book_id, names in sorted(book_groups.items(), key=lambda item: book_titles[item[0]])
        if book_id not in {str(value) for value in public_book_ids}
    )

    public_user_ids = set(
        LibraryGroupMembership.objects.filter(group=public).values_list("user_id", flat=True)
    )
    memberships = (
        LibraryGroupMembership.objects.filter(group_id__in=group_ids)
        .select_related("user", "group")
        .order_by("group__name", "user__username", "id")
    )
    user_groups: dict[str, set[str]] = {}
    usernames: dict[str, str] = {}
    membership_removals: list[MembershipRemovalPlan] = []
    for membership in memberships:
        user_id = str(membership.user_id)
        group_name = group_names[str(membership.group_id)]
        user_groups.setdefault(user_id, set()).add(group_name)
        usernames[user_id] = membership.user.get_username()
        membership_removals.append(
            MembershipRemovalPlan(
                membership_id=str(membership.id),
                user_id=user_id,
                username=membership.user.get_username(),
                group_id=str(membership.group_id),
                group_name=group_name,
                is_curator=membership.is_curator,
                expects_public_fallback=membership.user_id not in public_user_ids,
            )
        )
    user_fallbacks = tuple(
        UserPublicFallbackPlan(
            user_id=user_id,
            username=usernames[user_id],
            removed_group_names=tuple(sorted(names)),
        )
        for user_id, names in sorted(user_groups.items(), key=lambda item: usernames[item[0]])
        if user_id not in {str(value) for value in public_user_ids}
    )

    group_deletions = tuple(
        GroupDeletionPlan(group_id=str(group.id), name=group_names[str(group.id)])
        for group in custom_groups
    )
    summary = {
        "custom_groups": len(group_deletions),
        "shelves_moved": len(shelf_moves),
        "shelf_items_preserved": sum(op.item_count for op in shelf_moves),
        "book_assignments_removed": len(assignment_removals),
        "books_expected_public_fallback": len(book_fallbacks),
        "memberships_removed": len(membership_removals),
        "curator_assignments_removed": sum(1 for op in membership_removals if op.is_curator),
        "users_expected_public_fallback": len(user_fallbacks),
        "shelf_name_collisions": sum(1 for op in shelf_moves if op.name_collision),
    }

    full_plan = AdvancedGroupsDisablePlan(
        enabled_before=server_settings.advanced_library_groups_enabled(),
        public_group_id=public_id,
        public_group_name=public.name,
        phases=PHASES,
        shelf_moves=tuple(shelf_moves),
        book_assignment_removals=tuple(assignment_removals),
        book_public_fallbacks=book_fallbacks,
        membership_removals=tuple(membership_removals),
        user_public_fallbacks=user_fallbacks,
        group_deletions=group_deletions,
        summary=summary,
        shelf_name_collision_count=summary["shelf_name_collisions"],
        fingerprint="",
    )
    fingerprint = _make_fingerprint(full_plan)
    return replace(
        full_plan,
        shelf_moves=_limited(full_plan.shelf_moves, display_limit),
        book_assignment_removals=_limited(full_plan.book_assignment_removals, display_limit),
        book_public_fallbacks=_limited(full_plan.book_public_fallbacks, display_limit),
        membership_removals=_limited(full_plan.membership_removals, display_limit),
        user_public_fallbacks=_limited(full_plan.user_public_fallbacks, display_limit),
        group_deletions=_limited(full_plan.group_deletions, display_limit),
        fingerprint=fingerprint,
        display_limit=display_limit,
    )


def _custom_group_ids(plan: AdvancedGroupsDisablePlan) -> list[str]:
    return [op.group_id for op in plan.group_deletions]


def _assert_no_rows_remain(group_ids: list[str], *, phase: str) -> None:
    if Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group_id__in=group_ids).exists():
        raise AdvancedGroupsConsolidationError(f"{phase}: non-Public shelves remain.")
    if BookGroupAssignment.objects.filter(group_id__in=group_ids).exists():
        raise AdvancedGroupsConsolidationError(f"{phase}: non-Public book assignments remain.")
    if LibraryGroupMembership.objects.filter(group_id__in=group_ids).exists():
        raise AdvancedGroupsConsolidationError(f"{phase}: non-Public memberships remain.")


def execute_advanced_groups_disable_plan(
    *,
    actor,
    expected_fingerprint: str | None = None,
) -> AdvancedGroupsDisableResult:
    with transaction.atomic():
        plan = build_advanced_groups_disable_plan(display_limit=None)
        if expected_fingerprint and expected_fingerprint != plan.fingerprint:
            raise AdvancedGroupsPlanStale("The recovery plan changed. Review it again.")
        if not plan.enabled_before and not plan.has_custom_group_data:
            raise AdvancedGroupsConsolidationNotNeeded(
                "Advanced library groups are already disabled and no custom group data remains."
            )

        public = get_public_group()
        for op in plan.shelf_moves:
            shelf = Shelf.objects.select_for_update().get(pk=op.shelf_id)
            shelf.name = op.new_name
            shelf.owner_type = Shelf.OWNER_TYPE_GROUP
            shelf.owner_group = public
            shelf.owner_user = None
            shelf.save(update_fields=["name", "owner_type", "owner_group", "owner_user", "updated_at"])

        group_ids = _custom_group_ids(plan)
        if Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group_id__in=group_ids).exists():
            raise AdvancedGroupsConsolidationError("Shelf transfer failed: non-Public shelves remain.")

        for op in plan.book_assignment_removals:
            assignment = (
                BookGroupAssignment.objects.select_related("book", "group")
                .filter(pk=op.assignment_id)
                .first()
            )
            if assignment is not None:
                remove_book_from_group(actor=actor, book=assignment.book, group=assignment.group)
        if BookGroupAssignment.objects.filter(group_id__in=group_ids).exists():
            raise AdvancedGroupsConsolidationError(
                "Book assignment removal failed: non-Public assignments remain."
            )

        for op in plan.membership_removals:
            membership = (
                LibraryGroupMembership.objects.select_related("user", "group")
                .filter(pk=op.membership_id)
                .first()
            )
            if membership is not None:
                remove_user_from_group(actor=actor, membership=membership)
        if LibraryGroupMembership.objects.filter(group_id__in=group_ids).exists():
            raise AdvancedGroupsConsolidationError(
                "Membership removal failed: non-Public memberships remain."
            )

        _assert_no_rows_remain(group_ids, phase="Before group deletion")
        for op in plan.group_deletions:
            group = LibraryGroup.objects.filter(pk=op.group_id).first()
            if group is not None:
                delete_library_group(actor=actor, group=group)
        if LibraryGroup.objects.exclude(pk=public.pk).exists():
            raise AdvancedGroupsConsolidationError("Group deletion failed: non-Public groups remain.")

        server_settings.set_advanced_library_groups_enabled(False)

    logger.info("advanced groups consolidated into public", extra={"summary": plan.summary})
    return AdvancedGroupsDisableResult(plan=plan, summary=plan.summary)
