from django.core.management.base import BaseCommand

from shelves.unavailable_item_cleanup import (
    cleanup_unavailable_user_shelf_items,
    plan_unavailable_user_shelf_items,
)


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
        plan = plan_unavailable_user_shelf_items()
        self.stdout.write(f"Affected user-owned shelves: {plan.affected_shelf_count}")
        self.stdout.write(f"Unavailable shelf items: {plan.unavailable_item_count}")
        for entry in plan.shelves:
            self.stdout.write(
                f'- {entry.shelf_id} "{_safe_shelf_name(entry.shelf_name)}": '
                f"{entry.unavailable_item_count} unavailable item(s)"
            )

        if not options["apply"]:
            self.stdout.write("Dry run only; no changes were made.")
            return

        result = cleanup_unavailable_user_shelf_items()
        self.stdout.write(
            self.style.SUCCESS(
                "Cleanup complete: "
                f"{result.removed_item_count} item(s) removed from "
                f"{result.affected_shelf_count} user-owned shelf/shelves."
            )
        )
