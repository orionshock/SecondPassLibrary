from __future__ import annotations

from django.core.management.base import BaseCommand
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from library.imports.cli_sources import ImportSourceAdapter
from library.imports.results import ImportItemResult, ImportRunStats


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
            f"Destination free: {format_bytes(free_bytes)}"
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
            ("Processed", format_bytes(stats.processed_bytes)),
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


def format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    amount = float(max(0, value))
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "bytes" else f"{int(amount)} bytes"
        amount /= 1024
    return f"{int(value)} bytes"


def bounded_context(value, *, limit: int = 300) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _display(value) -> str:
    return escape(bounded_context(value))
