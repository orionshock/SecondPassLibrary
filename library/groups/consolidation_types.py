from __future__ import annotations

from dataclasses import dataclass


PHASES = (
    "Rename shelves",
    "Move shelves to Public Library",
    "Remove non-Public book/group associations and restore orphaned books to Public",
    "Remove group users/memberships/curators and restore orphaned users to Public",
    "Delete custom groups",
    "Disable advanced groups",
)


class AdvancedGroupsConsolidationError(RuntimeError):
    pass


class AdvancedGroupsPlanStale(AdvancedGroupsConsolidationError):
    pass


class AdvancedGroupsConsolidationNotNeeded(AdvancedGroupsConsolidationError):
    pass


@dataclass(frozen=True)
class ShelfMovePlan:
    shelf_id: str
    group_id: str
    group_name: str
    old_name: str
    new_name: str
    item_count: int
    name_collision: bool


@dataclass(frozen=True)
class BookAssignmentRemovalPlan:
    assignment_id: str
    book_id: str
    title: str
    group_id: str
    group_name: str
    expects_public_fallback: bool


@dataclass(frozen=True)
class BookPublicFallbackPlan:
    book_id: str
    title: str
    removed_group_names: tuple[str, ...]


@dataclass(frozen=True)
class MembershipRemovalPlan:
    membership_id: str
    user_id: str
    username: str
    group_id: str
    group_name: str
    is_curator: bool
    expects_public_fallback: bool


@dataclass(frozen=True)
class UserPublicFallbackPlan:
    user_id: str
    username: str
    removed_group_names: tuple[str, ...]


@dataclass(frozen=True)
class GroupDeletionPlan:
    group_id: str
    name: str


@dataclass(frozen=True)
class AdvancedGroupsDisablePlan:
    enabled_before: bool
    public_group_id: str
    public_group_name: str
    phases: tuple[str, ...]
    shelf_moves: tuple[ShelfMovePlan, ...]
    book_assignment_removals: tuple[BookAssignmentRemovalPlan, ...]
    book_public_fallbacks: tuple[BookPublicFallbackPlan, ...]
    membership_removals: tuple[MembershipRemovalPlan, ...]
    user_public_fallbacks: tuple[UserPublicFallbackPlan, ...]
    group_deletions: tuple[GroupDeletionPlan, ...]
    summary: dict[str, int]
    shelf_name_collision_count: int
    fingerprint: str
    display_limit: int | None = None

    @property
    def has_custom_group_data(self) -> bool:
        return any(
            (
                self.shelf_moves,
                self.book_assignment_removals,
                self.membership_removals,
                self.group_deletions,
            )
        )


@dataclass(frozen=True)
class AdvancedGroupsDisableResult:
    plan: AdvancedGroupsDisablePlan
    summary: dict[str, int]
