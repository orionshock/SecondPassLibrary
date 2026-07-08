from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any


PREVIEW_BOOK_LIMIT = 6


def include_preview_books(request) -> bool:
    value = request.query_params.get("include_preview_books")
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def attach_preview_books_from_queryset(
    *,
    parents: Iterable[Any],
    queryset: Iterable[Any],
    get_book: Callable[[Any], Any],
) -> None:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in queryset:
        grouped[str(getattr(row, "_preview_parent_id"))].append(get_book(row))
    for parent in parents:
        parent._preview_books = grouped.get(str(parent.id), [])
