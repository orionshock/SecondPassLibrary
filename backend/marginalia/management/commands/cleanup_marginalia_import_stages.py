from django.core.management.base import BaseCommand, CommandError

from maintenance.results import MaintenanceOperationError
from maintenance.cli_presentation import MaintenanceCliPresenter
from marginalia.imports.maintenance import execute_import_stage_cleanup


class Command(BaseCommand):
    help = "Remove expired Marginalia import stages and safe orphaned stage files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        presenter = MaintenanceCliPresenter(self)
        presenter.operation(
            name="Cleanup Marginalia Import Stages",
            mode="Dry run" if dry_run else "Apply",
        )
        try:
            result = execute_import_stage_cleanup(dry_run=dry_run)
        except MaintenanceOperationError as exc:
            if exc.result is not None:
                presenter.result(exc.result, status="Completed with failures")
            raise CommandError(str(exc)) from exc
        presenter.result(
            result,
            status="Dry run complete" if dry_run else "Succeeded",
        )
