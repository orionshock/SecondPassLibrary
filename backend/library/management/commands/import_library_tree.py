from pathlib import Path

from django.core.management.base import BaseCommand

from library.imports.cli_runner import run_cli_import
from library.imports.tree_source import TreeSource


class Command(BaseCommand):
    help = "Import logical EPUB/metadata.opf/cover candidates from a directory tree."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Local or read-only mounted directory tree.")

    def handle(self, *args, **options):
        run_cli_import(
            command=self,
            source=TreeSource(Path(options["path"])),
        )
