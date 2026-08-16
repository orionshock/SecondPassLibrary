from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from django.core.management.base import BaseCommand
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .results import MaintenanceResult, result_count_label


class MaintenanceCliPresenter:
    """Render bounded human-facing maintenance command output."""

    def __init__(self, command: BaseCommand):
        output = getattr(command.stdout, "_out", command.stdout)
        is_terminal = bool(getattr(output, "isatty", lambda: False)())
        use_color = is_terminal and not bool(getattr(command, "no_color", False))
        self.console = Console(
            file=output,
            force_terminal=is_terminal,
            color_system="auto" if use_color else None,
            width=None if is_terminal else 100,
        )

    def operation(self, *, name: str, mode: str) -> None:
        self.console.print(f"[bold]{_display(name)}[/bold]")
        self.console.print(f"Mode: {_display(mode)}")
        self.console.print()
        self.flush()

    def result(self, result: MaintenanceResult, *, status: str) -> None:
        self.counts(result.counts)
        self.status(status)

    def status(self, status: str) -> None:
        self.console.print(f"Result: [bold]{_display(status)}[/bold]")
        self.console.print()
        self.flush()

    def counts(self, counts: Mapping[str, int]) -> None:
        if not counts:
            return
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Metric")
        table.add_column("Count", justify="right")
        for key, value in counts.items():
            table.add_row(_display(result_count_label(key)), str(int(value)))
        self.console.print(table)
        self.console.print()
        self.flush()

    def detail_table(
        self,
        *,
        title: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[object]],
    ) -> None:
        rendered_rows = tuple(rows)
        if not rendered_rows:
            return
        table = Table(
            title=_display(title),
            box=None,
            pad_edge=False,
            header_style="bold",
        )
        for column in columns:
            table.add_column(_display(column), justify="right" if column == columns[-1] else "left")
        for row in rendered_rows:
            table.add_row(*(_display(value) for value in row))
        self.console.print(table)
        self.console.print()
        self.flush()

    def flush(self) -> None:
        flush = getattr(self.console.file, "flush", None)
        if callable(flush):
            flush()


def _bounded_text(value, *, limit: int = 160) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _display(value) -> str:
    return escape(_bounded_text(value))
