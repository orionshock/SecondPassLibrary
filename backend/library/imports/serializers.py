from __future__ import annotations

from django.db.models import Prefetch

from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_SKIPPED,
    ImportBatchResult,
    ImportItemResult,
)
from library.models import Book, BookAuthor


def import_item_payload(item: ImportItemResult, *, book_summary: dict | None = None) -> dict:
    payload = {
        "status": item.status,
        "source_label": item.source_label,
        "safe_message": item.safe_message,
    }
    if item.book is not None:
        payload["book_id"] = str(item.book.id)
        if book_summary is not None:
            payload.update(book_summary)
    return payload


def import_batch_payload(result: ImportBatchResult) -> dict:
    summaries = _book_summaries(result.items)
    return {
        "source_type": result.source_type,
        "source_label": result.source_label,
        "counts": {
            IMPORT_STATUS_IMPORTED: result.imported_count,
            IMPORT_STATUS_DUPLICATE: result.duplicate_count,
            IMPORT_STATUS_CONFLICT: result.conflict_count,
            IMPORT_STATUS_FAILED: result.failed_count,
            IMPORT_STATUS_SKIPPED: result.skipped_count,
        },
        "items": [
            import_item_payload(
                item,
                book_summary=summaries.get(item.book.pk) if item.book is not None else None,
            )
            for item in result.items
        ],
    }


def _book_summaries(items: list[ImportItemResult]) -> dict:
    book_ids = {item.book.pk for item in items if item.book is not None}
    if not book_ids:
        return {}
    books = (
        Book.objects.filter(pk__in=book_ids)
        .select_related("book_series__series")
        .prefetch_related(
            Prefetch(
                "book_authors",
                queryset=BookAuthor.objects.select_related("author").order_by("position", "id"),
            )
        )
    )
    summaries = {}
    for book in books:
        summary = {
            "title": book.title,
            "authors": [link.author.name for link in book.book_authors.all()],
        }
        series_link = getattr(book, "book_series", None)
        if series_link is not None:
            summary["series"] = series_link.series.name
            if series_link.series_index is not None:
                summary["series_index"] = str(series_link.series_index)
        summaries[book.pk] = summary
    return summaries
