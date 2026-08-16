from pathlib import Path

from django.core.management.base import BaseCommand

from library.imports.cli_runner import run_cli_import
from library.imports.cli_sources import AioZipSource


class Command(BaseCommand):
    help = "Import one large nested all-in-one EPUB/OPF/cover ZIP sequentially."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Large local ZIP file to import.")

    def handle(self, *args, **options):
        run_cli_import(
            command=self,
            source=AioZipSource(Path(options["path"])),
        )
