from __future__ import annotations

import logging

from .consolidation_types import AdvancedGroupsDisablePlan


logger = logging.getLogger("library.groups.consolidation")


def actor_name(actor) -> str:
    return getattr(actor, "get_username", lambda: str(actor))()


def recovery_started(*, actor, plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery started actor=%s public_group=%s public_group_id=%s custom_groups=%s",
        actor_name(actor),
        plan.public_group_name,
        plan.public_group_id,
        plan.summary["custom_groups"],
    )


def shelves_moved(plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery shelves moved count=%s shelf_items_preserved=%s",
        plan.summary["shelves_moved"],
        plan.summary["shelf_items_preserved"],
    )


def book_assignments_removed(plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery book assignments removed count=%s books_public_fallback=%s",
        plan.summary["book_assignments_removed"],
        plan.summary["books_expected_public_fallback"],
    )


def memberships_removed(plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery memberships removed count=%s curator_assignments_removed=%s users_public_fallback=%s",
        plan.summary["memberships_removed"],
        plan.summary["curator_assignments_removed"],
        plan.summary["users_expected_public_fallback"],
    )


def groups_deleted(plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery groups deleted count=%s",
        plan.summary["custom_groups"],
    )


def recovery_completed(*, duration_ms: int, plan: AdvancedGroupsDisablePlan) -> None:
    logger.info(
        "advanced groups recovery completed duration_ms=%s custom_groups=%s shelves_moved=%s book_assignments_removed=%s memberships_removed=%s",
        duration_ms,
        plan.summary["custom_groups"],
        plan.summary["shelves_moved"],
        plan.summary["book_assignments_removed"],
        plan.summary["memberships_removed"],
    )


def recovery_failed() -> None:
    logger.exception("advanced groups recovery failed")
