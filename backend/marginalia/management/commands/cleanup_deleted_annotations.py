from django.core.management.base import BaseCommand

from maintenance.cli_presentation import MaintenanceCliPresenter
from marginalia.annotations.maintenance import (
    DEFAULT_ANNOTATION_CLEANUP_LIMIT,
    MAX_ANNOTATION_CLEANUP_LIMIT,
    execute_deleted_annotation_cleanup,
)


class Command(BaseCommand):
    help = "Permanently delete expired Marginalia Annotation tombstones."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_ANNOTATION_CLEANUP_LIMIT,
            help=(
                "Maximum tombstones to process "
                f"(1-{MAX_ANNOTATION_CLEANUP_LIMIT})."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        presenter = MaintenanceCliPresenter(self)
        presenter.operation(
            name="Cleanup Deleted Marginalia Annotations",
            mode="Dry run" if dry_run else "Apply",
        )
        result = execute_deleted_annotation_cleanup(
            dry_run=dry_run,
            limit=options["limit"],
        )
        presenter.result(
            result,
            status="Dry run complete" if dry_run else "Succeeded",
        )
