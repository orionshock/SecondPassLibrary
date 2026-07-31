from django.core.management.base import BaseCommand, CommandError

from marginalia.imports.staging import cleanup_import_stages


class Command(BaseCommand):
    help = "Remove expired Marginalia import stages and safe orphaned stage files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        result = cleanup_import_stages(dry_run=options["dry_run"])
        self.stdout.write(
            "expired_stages_found={0} records_deleted={1} files_deleted={2} "
            "missing_files={3} failures={4}".format(
                result.expired_stages_found,
                result.records_deleted,
                result.files_deleted,
                result.missing_files,
                result.failures,
            )
        )
        if result.failures:
            raise CommandError(
                "Marginalia import stage cleanup completed with failures."
            )
