from django.core.management.base import BaseCommand, CommandError

from accounts.operational_logging import logger
from accounts.client_sessions.cleanup import (
    DEFAULT_PAIRING_CLEANUP_LIMIT,
    MAX_PAIRING_CLEANUP_LIMIT,
)
from accounts.client_sessions.maintenance import execute_pairing_request_cleanup
from maintenance.cli_presentation import MaintenanceCliPresenter


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
        dry_run = options["dry_run"]
        presenter = MaintenanceCliPresenter(self)
        presenter.operation(
            name="Cleanup Client Pairing Requests",
            mode="Dry run" if dry_run else "Apply",
        )
        try:
            result = execute_pairing_request_cleanup(
                dry_run=dry_run,
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

        presenter.result(
            result,
            status="Dry run complete" if dry_run else "Succeeded",
        )
