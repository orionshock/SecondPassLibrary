from django.core.management.base import BaseCommand, CommandError

from accounts.operational_logging import logger
from accounts.client_sessions.cleanup import (
    DEFAULT_PAIRING_CLEANUP_LIMIT,
    MAX_PAIRING_CLEANUP_LIMIT,
    cleanup_client_pairing_requests,
)


class Command(BaseCommand):
    help = "Remove expired and retained terminal client pairing requests."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_PAIRING_CLEANUP_LIMIT,
            help=(
                "Maximum rows to inspect/delete in one run "
                f"(1-{MAX_PAIRING_CLEANUP_LIMIT})."
            ),
        )

    def handle(self, *args, **options):
        try:
            result = cleanup_client_pairing_requests(
                dry_run=options["dry_run"],
                limit=options["limit"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            logger.error(
                "Client pairing cleanup failed: exception=%s",
                type(exc).__name__,
            )
            raise CommandError("Client pairing cleanup failed.") from exc

        self.stdout.write(
            "dry_run={0} eligible={1} selected={2} would_delete={3} deleted={4} "
            "skipped_limit={5} retained={6}".format(
                result.dry_run,
                result.eligible_count,
                result.selected_count,
                result.would_delete_count,
                result.deleted_count,
                result.skipped_limit_count,
                result.retained_count,
            )
        )
