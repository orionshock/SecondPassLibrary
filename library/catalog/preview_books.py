from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import F, QuerySet, Window
from django.db.models.functions import RowNumber

from library.models import Book, BookAuthor, BookSeries


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


def attach_author_preview_books(*, authors: Iterable[Any], visible_books: QuerySet[Book]) -> None:
    author_list = list(authors)
    if not author_list:
        return
    rows = (
        BookAuthor.objects.filter(author__in=author_list, book__in=visible_books)
        .select_related("book")
        .annotate(
            _preview_parent_id=F("author_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("author_id")],
                order_by=[
                    F("book__sort_title").asc(nulls_last=True),
                    F("book__title").asc(nulls_last=True),
                    F("book__id").asc(),
                ],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("author_id", "_preview_rank")
    )
    attach_preview_books_from_queryset(
        parents=author_list,
        queryset=rows,
        get_book=lambda row: row.book,
    )


def attach_series_preview_books(*, series: Iterable[Any], visible_books: QuerySet[Book]) -> None:
    series_list = list(series)
    if not series_list:
        return
    rows = (
        BookSeries.objects.filter(series__in=series_list, book__in=visible_books)
        .select_related("book")
        .annotate(
            _preview_parent_id=F("series_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("series_id")],
                order_by=[
                    F("series_index").asc(nulls_last=True),
                    F("book__sort_title").asc(nulls_last=True),
                    F("book__title").asc(nulls_last=True),
                    F("book__id").asc(),
                ],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("series_id", "_preview_rank")
    )
    attach_preview_books_from_queryset(
        parents=series_list,
        queryset=rows,
        get_book=lambda row: row.book,
    )
