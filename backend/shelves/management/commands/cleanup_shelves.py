from django.core.management.base import BaseCommand

from maintenance.cli_presentation import MaintenanceCliPresenter
from shelves.unavailable_item_cleanup import (
    plan_unavailable_user_shelf_items,
)
from shelves.maintenance import execute_unavailable_shelf_item_cleanup


def _safe_shelf_name(value: str) -> str:
    collapsed = " ".join(str(value or "").split())
    return collapsed[:77] + "..." if len(collapsed) > 80 else collapsed


class Command(BaseCommand):
    help = "Report or remove unavailable items from user-owned shelves."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Remove unavailable items. The default is a non-mutating dry run.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        presenter = MaintenanceCliPresenter(self)
        presenter.operation(
            name="Cleanup Unavailable Shelf Items",
            mode="Apply" if apply else "Dry run",
        )
        plan = plan_unavailable_user_shelf_items()
        presenter.counts(
            {
                "affected_shelves": plan.affected_shelf_count,
                "unavailable_items": plan.unavailable_item_count,
            }
        )
        presenter.detail_table(
            title="Affected Shelves",
            columns=("Shelf", "Unavailable items"),
            rows=(
                (_safe_shelf_name(entry.shelf_name), entry.unavailable_item_count)
                for entry in plan.shelves
            ),
        )

        if not apply:
            presenter.status("Dry run complete; no changes made")
            return

        result = execute_unavailable_shelf_item_cleanup()
        presenter.result(result, status="Succeeded")
