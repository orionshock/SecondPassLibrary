from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core import server_settings
from core.operational_logging import (
    info_on_commit,
    safe_log_label,
    suppress_state_change_logging,
    user_log_label,
)
from library.groups.book_assignments import remove_book_from_group
from library.groups.memberships import remove_user_from_group
from library.groups.public_group import get_public_group
from library.groups.services import delete_library_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.queries import invalidate_visible_books_cache
from shelves.models import Shelf, ShelfItem


logger = logging.getLogger(__name__)
MAX_SHELF_NAME_LENGTH = Shelf._meta.get_field("name").max_length

# Preview planning and execution share one fingerprinted state model so the
# destructive apply step cannot drift from the plan the operator reviewed.


class AdvancedGroupsConsolidationError(Exception):
    pass


class AdvancedGroupsConsolidationNotNeeded(Exception):
    pass


class AdvancedGroupsPlanStale(Exception):
    pass


@dataclass(frozen=True)
class ConsolidationSummary:
    custom_groups: int
    shelves_moved: int
    shelf_items_preserved: int
    book_assignments_removed: int
    books_expected_public_fallback: int
    memberships_removed: int
    curator_assignments_removed: int
    users_expected_public_fallback: int
    shelf_name_collisions: int


@dataclass(frozen=True)
class ShelfMove:
    shelf_id: str
    group_id: str
    group_name: str
    old_name: str
    new_name: str
    item_count: int
    name_collision: bool


@dataclass(frozen=True)
class BookAssignmentRemoval:
    book_id: str
    title: str
    group_id: str
    group_name: str


@dataclass(frozen=True)
class BookPublicFallback:
    book_id: str
    title: str
    removed_group_names: tuple[str, ...]


@dataclass(frozen=True)
class MembershipRemoval:
    user_id: str
    username: str
    group_id: str
    group_name: str
    is_curator: bool


@dataclass(frozen=True)
class UserPublicFallback:
    user_id: str
    username: str
    removed_group_names: tuple[str, ...]


@dataclass(frozen=True)
class GroupDeletion:
    group_id: str
    name: str


@dataclass(frozen=True)
class AdvancedGroupsDisablePlan:
    fingerprint: str
    enabled_before: bool
    public_group_id: str
    public_group_name: str
    summary: ConsolidationSummary
    shelf_moves: tuple[ShelfMove, ...]
    book_assignment_removals: tuple[BookAssignmentRemoval, ...]
    book_public_fallbacks: tuple[BookPublicFallback, ...]
    membership_removals: tuple[MembershipRemoval, ...]
    user_public_fallbacks: tuple[UserPublicFallback, ...]
    group_deletions: tuple[GroupDeletion, ...]
    display_limit: int | None


@dataclass(frozen=True)
class AdvancedGroupsDisableResult:
    plan: AdvancedGroupsDisablePlan
    summary: ConsolidationSummary
    public_curators_cleared: int


def build_advanced_groups_disable_plan(
    *, display_limit: int | None = None
) -> AdvancedGroupsDisablePlan:
    return _build_plan(display_limit=display_limit, lock=False)


def execute_advanced_groups_disable_plan(
    *, actor, expected_fingerprint: str
) -> AdvancedGroupsDisableResult:
    try:
        with transaction.atomic():
            plan = _build_plan(display_limit=None, lock=True)
            if not plan.enabled_before:
                raise AdvancedGroupsConsolidationNotNeeded(
                    "Advanced library groups are already disabled."
                )
            if plan.fingerprint != expected_fingerprint:
                raise AdvancedGroupsPlanStale(
                    "The advanced-groups state changed after preview. Review a new plan."
                )

            public_group = get_public_group()
            shelf_moves = {move.shelf_id: move for move in plan.shelf_moves}
            custom_groups = list(
                LibraryGroup.objects.select_for_update()
                .exclude(pk=public_group.pk)
                .order_by("name", "id")
            )
            with suppress_state_change_logging():
                for group in custom_groups:
                    _move_group_shelves(
                        group=group,
                        public_group=public_group,
                        shelf_moves=shelf_moves,
                    )
                    _remove_group_book_assignments(group=group, actor=actor)
                    _remove_group_memberships(group=group)
                    _assert_group_empty(group)
                    delete_library_group(group=group, actor=actor)

                public_curators_cleared = _clear_public_curators(public_group)
                _assert_postconditions(public_group)
                server_settings.set_advanced_library_groups_enabled(False)
            transaction.on_commit(invalidate_visible_books_cache)

        if plan.summary.shelf_name_collisions:
            logger.warning(
                "Resolved %d shelf name collision(s) while consolidating groups.",
                plan.summary.shelf_name_collisions,
            )
        if public_curators_cleared:
            logger.warning(
                "Cleared %d invalid curator membership(s) from the Public group.",
                public_curators_cleared,
            )
        public_group_id = str(plan.public_group_id)
        public_group_name = safe_log_label(
            plan.public_group_name,
            fallback=public_group_id,
        )
        actor_name = user_log_label(actor)
        info_on_commit(
            logger,
            "Advanced library groups consolidated: public_group=%s actor=%s "
            "groups=%d shelves=%d "
            "book_assignments=%d memberships=%d public_curators_cleared=%d",
            public_group_name,
            actor_name,
            plan.summary.custom_groups,
            plan.summary.shelves_moved,
            plan.summary.book_assignments_removed,
            plan.summary.memberships_removed,
            public_curators_cleared,
        )
        return AdvancedGroupsDisableResult(
            plan=plan,
            summary=plan.summary,
            public_curators_cleared=public_curators_cleared,
        )
    except (AdvancedGroupsConsolidationNotNeeded, AdvancedGroupsPlanStale):
        server_settings.clear_server_settings_cache()
        raise
    except Exception as exc:
        server_settings.clear_server_settings_cache()
        if isinstance(exc, AdvancedGroupsConsolidationError):
            raise
        raise AdvancedGroupsConsolidationError(str(exc)) from exc


def _build_plan(*, display_limit: int | None, lock: bool) -> AdvancedGroupsDisablePlan:
    public_group = get_public_group()
    group_queryset = LibraryGroup.objects.exclude(pk=public_group.pk).order_by("name", "id")
    if lock:
        group_queryset = group_queryset.select_for_update()
    groups = list(group_queryset)
    group_ids = [group.pk for group in groups]

    shelves = list(
        Shelf.objects.filter(owner_group_id__in=group_ids)
        .annotate(_item_count=Count("items"))
        .order_by("owner_group__name", "name", "created_at", "id")
    )
    assignments = list(
        BookGroupAssignment.objects.filter(group_id__in=group_ids)
        .select_related("book", "group")
        .order_by("group__name", "book__sort_title", "book__title", "id")
    )
    memberships = list(
        LibraryGroupMembership.objects.filter(group_id__in=group_ids)
        .select_related("user", "group")
        .order_by("group__name", "user__username", "id")
    )

    shelf_moves = _plan_shelf_moves(public_group=public_group, shelves=shelves)
    book_removals = tuple(
        BookAssignmentRemoval(
            book_id=str(row.book_id),
            title=row.book.title,
            group_id=str(row.group_id),
            group_name=row.group.name,
        )
        for row in assignments
    )
    membership_removals = tuple(
        MembershipRemoval(
            user_id=str(row.user_id),
            username=row.user.get_username(),
            group_id=str(row.group_id),
            group_name=row.group.name,
            is_curator=row.is_curator,
        )
        for row in memberships
    )
    book_fallbacks = _book_fallbacks(assignments=assignments, public_group=public_group)
    user_fallbacks = _user_fallbacks(memberships=memberships, public_group=public_group)
    group_deletions = tuple(
        GroupDeletion(group_id=str(group.id), name=group.name) for group in groups
    )
    summary = ConsolidationSummary(
        custom_groups=len(groups),
        shelves_moved=len(shelf_moves),
        shelf_items_preserved=sum(move.item_count for move in shelf_moves),
        book_assignments_removed=len(book_removals),
        books_expected_public_fallback=len(book_fallbacks),
        memberships_removed=len(membership_removals),
        curator_assignments_removed=sum(row.is_curator for row in memberships),
        users_expected_public_fallback=len(user_fallbacks),
        shelf_name_collisions=sum(move.name_collision for move in shelf_moves),
    )
    fingerprint = _state_fingerprint(public_group=public_group)
    limit = None if display_limit is None else max(0, int(display_limit))
    return AdvancedGroupsDisablePlan(
        fingerprint=fingerprint,
        enabled_before=server_settings.advanced_library_groups_enabled(),
        public_group_id=str(public_group.id),
        public_group_name=public_group.name,
        summary=summary,
        shelf_moves=_limited(shelf_moves, limit),
        book_assignment_removals=_limited(book_removals, limit),
        book_public_fallbacks=_limited(book_fallbacks, limit),
        membership_removals=_limited(membership_removals, limit),
        user_public_fallbacks=_limited(user_fallbacks, limit),
        group_deletions=_limited(group_deletions, limit),
        display_limit=limit,
    )


def _plan_shelf_moves(*, public_group, shelves) -> tuple[ShelfMove, ...]:
    used_names = set(
        Shelf.objects.filter(owner_group=public_group).values_list("name", flat=True)
    )
    moves = []
    for shelf in shelves:
        desired = f"{shelf.owner_group.name} / {shelf.name}"
        new_name = _unique_shelf_name(desired, used_names)
        used_names.add(new_name)
        moves.append(
            ShelfMove(
                shelf_id=str(shelf.id),
                group_id=str(shelf.owner_group_id),
                group_name=shelf.owner_group.name,
                old_name=shelf.name,
                new_name=new_name,
                item_count=shelf._item_count,
                name_collision=new_name != _truncate_name(desired, ""),
            )
        )
    return tuple(moves)


def _unique_shelf_name(desired: str, used_names: set[str]) -> str:
    candidate = _truncate_name(desired, "")
    if candidate not in used_names:
        return candidate
    counter = 2
    while True:
        suffix = f" ({counter})"
        candidate = _truncate_name(desired, suffix)
        if candidate not in used_names:
            return candidate
        counter += 1


def _truncate_name(value: str, suffix: str) -> str:
    return f"{value[: MAX_SHELF_NAME_LENGTH - len(suffix)]}{suffix}"


def _book_fallbacks(*, assignments, public_group) -> tuple[BookPublicFallback, ...]:
    affected = {row.book_id: row.book for row in assignments}
    public_ids = set(
        BookGroupAssignment.objects.filter(
            book_id__in=affected,
            group=public_group,
        ).values_list("book_id", flat=True)
    )
    group_names: dict[object, list[str]] = {}
    for row in assignments:
        group_names.setdefault(row.book_id, []).append(row.group.name)
    return tuple(
        BookPublicFallback(
            book_id=str(book_id),
            title=book.title,
            removed_group_names=tuple(group_names[book_id]),
        )
        for book_id, book in sorted(affected.items(), key=lambda item: str(item[0]))
        if book_id not in public_ids
    )


def _user_fallbacks(*, memberships, public_group) -> tuple[UserPublicFallback, ...]:
    affected = {row.user_id: row.user for row in memberships}
    public_ids = set(
        LibraryGroupMembership.objects.filter(
            user_id__in=affected,
            group=public_group,
        ).values_list("user_id", flat=True)
    )
    group_names: dict[object, list[str]] = {}
    for row in memberships:
        group_names.setdefault(row.user_id, []).append(row.group.name)
    return tuple(
        UserPublicFallback(
            user_id=str(user_id),
            username=user.get_username(),
            removed_group_names=tuple(group_names[user_id]),
        )
        for user_id, user in sorted(affected.items(), key=lambda item: str(item[0]))
        if user_id not in public_ids
    )


def _state_fingerprint(*, public_group) -> str:
    group_shelves = Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP)
    state = {
        "enabled": server_settings.advanced_library_groups_enabled(),
        "public_group_id": str(public_group.id),
        "groups": list(
            LibraryGroup.objects.order_by("id").values_list(
                "id", "name", "description", "updated_at"
            )
        ),
        "books": list(
            Book.objects.order_by("id").values_list("id", "title", "updated_at")
        ),
        "users": list(
            get_user_model().objects.order_by("id").values_list(
                "id", "username", "is_active"
            )
        ),
        "shelves": list(
            group_shelves.order_by("id").values_list(
                "id", "name", "description", "owner_type", "owner_user_id",
                "owner_group_id", "visibility", "created_by_id", "updated_at",
            )
        ),
        "shelf_items": list(
            ShelfItem.objects.filter(shelf__in=group_shelves).order_by("id").values_list(
                "id", "shelf_id", "book_id", "position", "added_by_id", "updated_at"
            )
        ),
        "book_assignments": list(
            BookGroupAssignment.objects.order_by("id").values_list(
                "id", "book_id", "group_id", "added_by_id", "updated_at"
            )
        ),
        "memberships": list(
            LibraryGroupMembership.objects.order_by("id").values_list(
                "id", "user_id", "group_id", "is_curator", "updated_at"
            )
        ),
    }
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _limited(rows: tuple, limit: int | None) -> tuple:
    return rows if limit is None else rows[:limit]


def _move_group_shelves(*, group, public_group, shelf_moves) -> None:
    shelves = list(
        Shelf.objects.select_for_update()
        .filter(owner_group=group)
        .order_by("name", "created_at", "id")
    )
    for shelf in shelves:
        move = shelf_moves[str(shelf.id)]
        shelf.name = move.new_name
        shelf.owner_group = public_group
        shelf.visibility = Shelf.VISIBILITY_PRIVATE
        shelf.save(update_fields=["name", "owner_group", "visibility", "updated_at"])


def _remove_group_book_assignments(*, group, actor) -> None:
    assignments = list(
        BookGroupAssignment.objects.filter(group=group)
        .select_related("book")
        .order_by("book__sort_title", "book__title", "id")
    )
    for assignment in assignments:
        remove_book_from_group(book=assignment.book, group=group, actor=actor)


def _remove_group_memberships(*, group) -> None:
    memberships = list(
        LibraryGroupMembership.objects.filter(group=group)
        .select_related("user")
        .order_by("user__username", "id")
    )
    for membership in memberships:
        remove_user_from_group(user=membership.user, group=group)


def _assert_group_empty(group) -> None:
    if group.shelves_owned.exists():
        raise AdvancedGroupsConsolidationError("Custom group still owns shelves.")
    if group.book_assignments.exists():
        raise AdvancedGroupsConsolidationError("Custom group still has book assignments.")
    if group.memberships.exists():
        raise AdvancedGroupsConsolidationError("Custom group still has memberships.")


def _clear_public_curators(public_group) -> int:
    queryset = LibraryGroupMembership.objects.filter(
        group=public_group,
        is_curator=True,
    )
    count = queryset.count()
    if count:
        queryset.update(is_curator=False, updated_at=timezone.now())
    return count


def _assert_postconditions(public_group) -> None:
    if not LibraryGroup.objects.filter(pk=public_group.pk).exists():
        raise AdvancedGroupsConsolidationError("Public group no longer exists.")
    if get_user_model().objects.exclude(library_group_memberships__isnull=False).exists():
        raise AdvancedGroupsConsolidationError("A user has no library-group membership.")
    if Book.objects.exclude(group_assignments__isnull=False).exists():
        raise AdvancedGroupsConsolidationError("A book has no library-group assignment.")
    if LibraryGroupMembership.objects.filter(
        group=public_group,
        is_curator=True,
    ).exists():
        raise AdvancedGroupsConsolidationError("Public group has curator memberships.")
