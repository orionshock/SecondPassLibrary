from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.imports.results import (
    IMPORT_STATUS_FAILED,
    ImportBatchResult,
    ImportItemResult,
)
from library.queries import defer_visible_books_cache_invalidation


SUPPORTED_SUFFIXES = {".epub", ".zip"}


class Command(BaseCommand):
    help = "Import EPUB or ZIP files into the library."

    def add_arguments(self, parser):
        parser.add_argument("path", help="EPUB file, ZIP file, or non-recursive directory to import.")

    def handle(self, *args, **options):
        source = Path(options["path"])
        if not source.exists():
            raise CommandError(f"Import path does not exist: {source}")
        if not source.is_file() and not source.is_dir():
            raise CommandError(f"Import path is not a file or directory: {source}")

        result = _import_path(source)
        _write_batch_result(self, result)
        if result.failed_count or result.conflict_count:
            raise CommandError("Import completed with failed or conflicting items.")


def _import_path(source: Path) -> ImportBatchResult:
    if source.is_dir():
        return _import_directory(source)
    if source.suffix.casefold() == ".epub":
        return _import_epub_path(source)
    if source.suffix.casefold() == ".zip":
        return _import_zip_path(source)
    raise CommandError(f"Unsupported import source: {source}")


def _import_directory(source: Path) -> ImportBatchResult:
    batch = ImportBatchResult(
        source_type="directory",
        source_label=source.name or str(source),
        discovered_count=0,
    )
    candidates = [
        child
        for child in source.iterdir()
        if child.is_file() and child.suffix.casefold() in SUPPORTED_SUFFIXES
    ]
    with defer_visible_books_cache_invalidation():
        for child in sorted(candidates, key=lambda path: (path.name.casefold(), path.name)):
            item_result = _import_directory_child_path(child)
            if isinstance(item_result, ImportBatchResult):
                batch.items.extend(item_result.items)
                batch.discovered_count = (batch.discovered_count or 0) + item_result.total_found
            else:
                batch.items.append(item_result)
                batch.discovered_count = (batch.discovered_count or 0) + 1
    return batch


def _import_file_path(source: Path) -> ImportItemResult | ImportBatchResult:
    if source.suffix.casefold() == ".epub":
        return _import_epub_path(source).items[0]
    if source.suffix.casefold() == ".zip":
        return _import_zip_path(source)
    raise CommandError(f"Unsupported import source: {source}")


def _import_directory_child_path(source: Path) -> ImportItemResult | ImportBatchResult:
    try:
        return _import_file_path(source)
    except (CommandError, OSError):
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source.name,
            safe_message="Could not read import file.",
        )


def _import_epub_path(source: Path) -> ImportBatchResult:
    try:
        with source.open("rb") as fp:
            item = import_epub_file(fp, source_filename=source.name, actor=None)
    except OSError as exc:
        raise CommandError(f"Could not read import file: {source}") from exc
    return ImportBatchResult(
        source_type="epub",
        source_label=source.name,
        items=[item],
        discovered_count=1,
    )


def _import_zip_path(source: Path) -> ImportBatchResult:
    try:
        with source.open("rb") as fp:
            return import_zip_file(fp, source_filename=source.name, actor=None)
    except OSError as exc:
        raise CommandError(f"Could not read import file: {source}") from exc


def _write_batch_result(command: BaseCommand, result: ImportBatchResult) -> None:
    for item in result.items:
        message = f" - {item.safe_message}" if item.safe_message else ""
        command.stdout.write(f"[{item.status}] {item.source_label}{message}")
    command.stdout.write("Summary:")
    command.stdout.write(f"imported: {result.imported_count}")
    command.stdout.write(f"duplicate: {result.duplicate_count}")
    command.stdout.write(f"conflict: {result.conflict_count}")
    command.stdout.write(f"failed: {result.failed_count}")
    command.stdout.write(f"skipped: {result.skipped_count}")
    if result.failed_count or result.conflict_count:
        command.stderr.write(
            f"Import finished with {result.failed_count} failed and "
            f"{result.conflict_count} conflicting item(s)."
        )
