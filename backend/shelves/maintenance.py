from maintenance.results import MaintenanceResult

from .unavailable_item_cleanup import (
    cleanup_unavailable_user_shelf_items,
    plan_unavailable_user_shelf_items,
)


def execute_unavailable_shelf_item_cleanup(
    *, apply: bool = True
) -> MaintenanceResult:
    if not apply:
        plan = plan_unavailable_user_shelf_items()
        return MaintenanceResult(
            summary=(
                f"Dry run only; {plan.unavailable_item_count} unavailable item(s) "
                f"found on {plan.affected_shelf_count} user-owned shelf/shelves."
            ),
            counts={
                "affected_shelves": plan.affected_shelf_count,
                "unavailable_items": plan.unavailable_item_count,
            },
        )
    result = cleanup_unavailable_user_shelf_items()
    return MaintenanceResult(
        summary=(
            f"Cleanup complete: {result.removed_item_count} item(s) removed from "
            f"{result.affected_shelf_count} user-owned shelf/shelves."
        ),
        counts={
            "affected_shelves": result.affected_shelf_count,
            "removed_items": result.removed_item_count,
        },
    )
