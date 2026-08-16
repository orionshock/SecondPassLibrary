from __future__ import annotations

import logging
from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from library.imports.cli_sources import (
    ImportSourceAdapter,
    ImportSourceFatalError,
)
from library.imports.epub import import_epub_file
from library.imports.results import ImportItemResult, ImportRunStats
from library.queries import defer_visible_books_cache_invalidation


MIN_DESTINATION_FREE_BYTES = 1024 * 1024 * 1024
PROGRESS_INTERVAL = 100
logger = logging.getLogger(__name__)


class ImportCliPresenter:
    def __init__(self, command: BaseCommand):
        output = command.stdout
        is_terminal = bool(getattr(output, "isatty", lambda: False)())
        use_color = is_terminal and not bool(getattr(command, "no_color", False))
        self.console = Console(
            file=output,
            force_terminal=is_terminal,
            color_system="auto" if use_color else None,
        )

    def run_started(self, *, source, free_bytes: int | None) -> None:
        self.console.print(f"[bold]Library import — {source.method}[/bold]")
        self.console.print(f"Source: {_display(source.source)}")
        self.console.print(f"Limits: {_display(source.limit_description)}")
        self.console.print(
            f"Destination free: {_format_bytes(free_bytes)}"
            if free_bytes is not None
            else "Destination free: unavailable"
        )
        self.console.print()
        self.flush()

    def candidate_started(self, ordinal: int, event) -> None:
        self.console.print(f"[bold]Candidate {ordinal}[/bold]")
        self.console.print(f"  Source    {_display(event.source_label)}")
        if event.candidate is not None and event.candidate.metadata_label:
            self.console.print(f"  Metadata  {_display(event.candidate.metadata_label)}")
        self.console.print("  Status    Starting")
        self.flush()

    def candidate_completed(self, result: ImportItemResult) -> None:
        labels = {
            "imported": "[green]Imported[/green]",
            "duplicate": "[cyan]Duplicate[/cyan]",
            "conflict": "[yellow]Conflict[/yellow]",
            "skipped": "[yellow]Skipped[/yellow]",
            "failed": "[red]Failed[/red]",
        }
        if result.title:
            self.console.print(f"  Title     {_display(result.title)}")
        if result.authors:
            self.console.print(f"  Authors   {_display(', '.join(result.authors))}")
        self.console.print(f"  Result    {labels.get(result.status, result.status.title())}")
        if result.book is not None:
            self.console.print(f"  Book ID   {result.book.pk}")
        if result.safe_message and result.status not in {"imported"}:
            self.console.print(f"  Detail    {_display(result.safe_message)}")
        self.console.print()
        self.flush()

    def progress(self, stats: ImportRunStats) -> None:
        self.console.print(
            f"Progress: {stats.last_completed_candidate:,} candidates completed; "
            f"{stats.imported:,} imported; {stats.failed:,} failed"
        )
        self.flush()

    def fatal(self, message: str, *, stats: ImportRunStats, next_source: str = "") -> None:
        self.console.print("[bold red]Import stopped[/bold red]")
        self.console.print(f"  Reason         {message}")
        self.console.print(f"  Last completed {stats.last_completed_candidate or 'none'}")
        if next_source:
            self.console.print(f"  Next source    {next_source}")
        self.console.print()
        self.flush()

    def interrupted(self, stats: ImportRunStats) -> None:
        self.console.print(
            f"[bold yellow]Interrupted after candidate "
            f"{stats.last_completed_candidate or 0}.[/bold yellow]"
        )
        self.flush()

    def summary(self, stats: ImportRunStats, *, source: ImportSourceAdapter) -> None:
        table = Table(title="Import summary", show_header=False, box=None, pad_edge=False)
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right")
        for label, value in (
            ("Discovered", stats.discovered),
            ("Presented", stats.presented),
            ("Imported", stats.imported),
            ("Duplicates", stats.duplicates),
            ("Conflicts", stats.conflicts),
            ("Skipped", stats.skipped),
            ("Failed", stats.failed),
            ("Source failures", stats.source_failures),
            ("Ambiguous", stats.ambiguous),
            ("Processed", _format_bytes(stats.processed_bytes)),
            ("Skipped symlinks", source.skipped_symlinks),
            ("Skipped archive members", source.skipped_members),
        ):
            table.add_row(label, str(value))
        self.console.print(table)
        self.flush()

    def flush(self) -> None:
        flush = getattr(self.console.file, "flush", None)
        if callable(flush):
            flush()


def run_cli_import(*, command: BaseCommand, source: ImportSourceAdapter) -> ImportRunStats:
    presenter = ImportCliPresenter(command)
    stats = ImportRunStats(source_method=source.method)
    free_bytes = _destination_free_bytes()
    presenter.run_started(source=source, free_bytes=free_bytes)
    logger.info(
        "CLI library import started: source_method=%s source=%s limits=%s",
        source.method,
        _bounded_context(source.source),
        source.limit_description,
    )
    if free_bytes is not None and free_bytes < MIN_DESTINATION_FREE_BYTES:
        message = _low_space_message(free_bytes)
        presenter.fatal(message, stats=stats)
        raise CommandError(message)

    try:
        with defer_visible_books_cache_invalidation():
            for ordinal, event in enumerate(source.iter_events(), start=1):
                stats.discovered += 1
                presenter.candidate_started(ordinal, event)
                if event.candidate is not None:
                    free_bytes = _destination_free_bytes()
                    required = MIN_DESTINATION_FREE_BYTES + event.candidate.file_size
                    if free_bytes is not None and free_bytes < required:
                        message = _low_space_message(free_bytes)
                        presenter.fatal(
                            message,
                            stats=stats,
                            next_source=event.source_label,
                        )
                        raise CommandError(message)
                    stats.presented += 1
                    logger.info(
                        "CLI import candidate presented: source_method=%s ordinal=%d source=%s",
                        source.method,
                        ordinal,
                        _bounded_context(event.source_label),
                    )
                    candidate = event.candidate
                    result = import_epub_file(
                        candidate.file_obj,
                        source_filename=candidate.epub_filename,
                        source_label=candidate.source_label,
                        source_method=candidate.source_method,
                        sidecar_opf=candidate.sidecar_opf,
                        sidecar_cover_bytes=candidate.sidecar_cover_bytes,
                        actor=None,
                    )
                else:
                    result = event.result
                    logger.warning(
                        "CLI import source candidate not presented: "
                        "source_method=%s ordinal=%d category=%s",
                        source.method,
                        ordinal,
                        result.error_category if result is not None else "unknown",
                    )
                if result is None:
                    raise ImportSourceFatalError("Source adapter returned no candidate result.")
                stats.record(
                    result,
                    source_failure=event.candidate is None and result.status == "failed",
                    ambiguous=event.ambiguous,
                    processed_bytes=event.processed_bytes,
                )
                stats.last_completed_candidate = ordinal
                presenter.candidate_completed(result)
                if ordinal % PROGRESS_INTERVAL == 0:
                    presenter.progress(stats)
                    logger.info(
                        "CLI library import progress: source_method=%s completed=%d "
                        "imported=%d failed=%d",
                        source.method,
                        ordinal,
                        stats.imported,
                        stats.failed,
                    )
                if result.error_category == "io_error":
                    raise ImportSourceFatalError(
                        "Candidate I/O or storage failed; continuing may be unsafe."
                    )
    except KeyboardInterrupt:
        presenter.interrupted(stats)
        logger.warning(
            "CLI library import interrupted: source_method=%s completed=%d",
            source.method,
            stats.last_completed_candidate,
        )
        raise
    except ImportSourceFatalError as exc:
        presenter.fatal(str(exc), stats=stats)
        logger.error(
            "CLI library import stopped: source_method=%s completed=%d reason=%s",
            source.method,
            stats.last_completed_candidate,
            type(exc).__name__,
        )
        raise CommandError(str(exc)) from exc

    presenter.summary(stats, source=source)
    logger.info(
        "CLI library import completed: source_method=%s discovered=%d presented=%d "
        "imported=%d duplicate=%d conflict=%d skipped=%d failed=%d "
        "source_failures=%d ambiguous=%d processed_bytes=%d",
        source.method,
        stats.discovered,
        stats.presented,
        stats.imported,
        stats.duplicates,
        stats.conflicts,
        stats.skipped,
        stats.failed,
        stats.source_failures,
        stats.ambiguous,
        stats.processed_bytes,
    )
    if stats.failed or stats.conflicts:
        raise CommandError(
            "Import completed with failed, conflicting, or ambiguous candidates."
        )
    return stats


def _destination_free_bytes() -> int | None:
    path = Path(settings.MEDIA_ROOT)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _low_space_message(free_bytes: int) -> str:
    return (
        f"Destination free space is {_format_bytes(free_bytes)}; at least "
        f"{_format_bytes(MIN_DESTINATION_FREE_BYTES)} must remain."
    )


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    amount = float(max(0, value))
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "bytes" else f"{int(amount)} bytes"
        amount /= 1024
    return f"{int(value)} bytes"


def _bounded_context(value, *, limit: int = 300) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _display(value) -> str:
    return escape(_bounded_context(value))
