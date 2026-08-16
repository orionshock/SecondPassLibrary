from django.core.management.base import BaseCommand, CommandError

from maintenance.results import MaintenanceOperationError
from marginalia.imports.maintenance import execute_import_stage_cleanup


class Command(BaseCommand):
    help = "Remove expired Marginalia import stages and safe orphaned stage files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            result = execute_import_stage_cleanup(dry_run=options["dry_run"])
        except MaintenanceOperationError as exc:
            if exc.result is not None:
                self.stdout.write(exc.result.summary)
            raise CommandError(str(exc)) from exc
        self.stdout.write(result.summary)
