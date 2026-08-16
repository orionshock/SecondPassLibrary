from pathlib import Path

from django.core.management.base import BaseCommand

from library.imports.cli_runner import run_cli_import
from library.imports.cli_sources import FolderOfArchivesSource


class Command(BaseCommand):
    help = (
        "Recursively import individual EPUB and ZIP sources from an operator folder."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            help="Directory tree, EPUB file, or per-Book ZIP file to import.",
        )

    def handle(self, *args, **options):
        run_cli_import(
            command=self,
            source=FolderOfArchivesSource(Path(options["path"])),
        )
