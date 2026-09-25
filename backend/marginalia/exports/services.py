from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import Count, IntegerField, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Length
from django.utils import timezone

from library.models import Book, BookAuthor
from marginalia.archives import render_archive_json, serialize_archive
from marginalia.models import Annotation, ReadingSession


# Exports are deliberately buffered, so reject pathological work before archive
# materialization and enforce a hard bound on the one final JSON byte string.
MAX_SELECTED_EXPORT_SESSION_IDS = 500
MAX_FULL_EXPORT_SESSIONS = 5_000
MAX_EXPORT_ANNOTATIONS = 50_000
MAX_EXPORT_BYTES = 16 * 1024 * 1024
_BASE_ESTIMATED_BYTES = 4 * 1024
# The archive writes one Book object per distinct represented Book and one author
# string per BookAuthor link. These fixed allowances cover their JSON structure;
# actual title, checksum, and author-name characters retain the worst-case 6-byte
# UTF-8/JSON escaping multiplier used by Session and annotation text.
_BOOK_ESTIMATED_OVERHEAD = 256
_AUTHOR_ESTIMATED_OVERHEAD = 16
_SESSION_ESTIMATED_OVERHEAD = 512
_ANNOTATION_ESTIMATED_OVERHEAD = 256
_TEXT_ESTIMATE_MULTIPLIER = 6
logger = logging.getLogger(__name__)


class NoExportableSessionsError(ValueError):
    pass


class SelectedSessionNotFoundError(LookupError):
    pass


class ExportTooLargeError(ValueError):
    def __init__(self, *, mode: str, reason: str, maximum: int) -> None:
        super().__init__()
        self.mode = mode
        self.reason = reason
        self.maximum = maximum


@dataclass(frozen=True, slots=True)
class MarginaliaExportDocument:
    content: bytes
    generated_at: datetime


def export_all_marginalia(
    *,
    user,
    include_empty_sessions: bool = False,
) -> MarginaliaExportDocument:
    sessions = ReadingSession.objects.filter(user=user)
    return _build_export(
        user=user,
        mode="full",
        sessions=sessions,
        include_empty_sessions=include_empty_sessions,
        maximum_sessions=MAX_FULL_EXPORT_SESSIONS,
    )


def export_selected_marginalia(
    *,
    user,
    reading_session_ids: list[UUID],
    include_empty_sessions: bool = False,
) -> MarginaliaExportDocument:
    if len(reading_session_ids) > MAX_SELECTED_EXPORT_SESSION_IDS:
        _reject_export(
            user=user,
            mode="selected",
            reason="selected_sessions",
            session_count=len(reading_session_ids),
            annotation_count=None,
            maximum=MAX_SELECTED_EXPORT_SESSION_IDS,
        )
    sessions = ReadingSession.objects.filter(
        user=user,
        pk__in=reading_session_ids,
    )
    if sessions.count() != len(reading_session_ids):
        raise SelectedSessionNotFoundError
    return _build_export(
        user=user,
        mode="selected",
        sessions=sessions,
        include_empty_sessions=include_empty_sessions,
        maximum_sessions=MAX_SELECTED_EXPORT_SESSION_IDS,
    )


def _build_export(
    *,
    user,
    mode: str,
    sessions,
    include_empty_sessions: bool,
    maximum_sessions: int,
) -> MarginaliaExportDocument:
    stats = _export_stats(
        sessions,
        include_empty_sessions=include_empty_sessions,
    )
    if stats.session_count > maximum_sessions:
        _reject_export(
            user=user,
            mode=mode,
            reason="full_sessions" if mode == "full" else "selected_sessions",
            session_count=stats.session_count,
            annotation_count=stats.annotation_count,
            maximum=maximum_sessions,
        )
    if stats.annotation_count > MAX_EXPORT_ANNOTATIONS:
        _reject_export(
            user=user,
            mode=mode,
            reason="annotations",
            session_count=stats.session_count,
            annotation_count=stats.annotation_count,
            maximum=MAX_EXPORT_ANNOTATIONS,
        )
    if stats.estimated_bytes > MAX_EXPORT_BYTES:
        _reject_export(
            user=user,
            mode=mode,
            reason="estimated_archive_bytes",
            session_count=stats.session_count,
            annotation_count=stats.annotation_count,
            maximum=MAX_EXPORT_BYTES,
        )

    generated_at = timezone.now()
    archive = serialize_archive(
        sessions,
        generated_at=generated_at,
        include_empty_sessions=include_empty_sessions,
    )
    if not archive.books:
        raise NoExportableSessionsError
    content = render_archive_json(archive)
    if len(content) > MAX_EXPORT_BYTES:
        _reject_export(
            user=user,
            mode=mode,
            reason="archive_bytes",
            session_count=stats.session_count,
            annotation_count=stats.annotation_count,
            maximum=MAX_EXPORT_BYTES,
        )
    return MarginaliaExportDocument(
        content=content,
        generated_at=generated_at,
    )


@dataclass(frozen=True, slots=True)
class _ExportStats:
    session_count: int
    annotation_count: int
    book_count: int
    author_count: int
    estimated_bytes: int


def _export_stats(sessions, *, include_empty_sessions: bool) -> _ExportStats:
    session_stats = sessions.aggregate(
        count=Count("pk"),
        text_characters=_text_character_sum(
            "name",
            "notes",
            "progress_location",
            "progress_location_label",
        ),
    )
    annotations = Annotation.objects.filter(
        session__in=sessions,
        is_deleted=False,
    )
    annotation_stats = annotations.aggregate(
        count=Count("pk"),
        text_characters=_text_character_sum(
            "client_id",
            "location",
            "location_label",
            "highlight_text",
            "quote_prefix",
            "quote_suffix",
            "highlight_color",
            "comment_text",
        ),
    )
    represented_sessions = sessions
    if not include_empty_sessions:
        represented_sessions = sessions.filter(annotations__is_deleted=False)
    represented_book_ids = represented_sessions.order_by().values("book_id").distinct()
    books = Book.objects.filter(pk__in=Subquery(represented_book_ids))
    book_stats = books.aggregate(
        count=Count("pk"),
        text_characters=_text_character_sum("title", "checksum"),
    )
    book_authors = BookAuthor.objects.filter(
        book_id__in=Subquery(represented_book_ids),
    )
    author_stats = book_authors.aggregate(
        count=Count("pk"),
        text_characters=_text_character_sum("author__name"),
    )
    session_count = int(session_stats["count"])
    annotation_count = int(annotation_stats["count"])
    book_count = int(book_stats["count"])
    author_count = int(author_stats["count"])
    text_characters = (
        int(session_stats["text_characters"])
        + int(annotation_stats["text_characters"])
        + int(book_stats["text_characters"])
        + int(author_stats["text_characters"])
    )
    estimated_bytes = (
        _BASE_ESTIMATED_BYTES
        + book_count * _BOOK_ESTIMATED_OVERHEAD
        + author_count * _AUTHOR_ESTIMATED_OVERHEAD
        + session_count * _SESSION_ESTIMATED_OVERHEAD
        + annotation_count * _ANNOTATION_ESTIMATED_OVERHEAD
        + text_characters * _TEXT_ESTIMATE_MULTIPLIER
    )
    return _ExportStats(
        session_count=session_count,
        annotation_count=annotation_count,
        book_count=book_count,
        author_count=author_count,
        estimated_bytes=estimated_bytes,
    )


def _text_character_sum(*fields: str):
    row_length = Value(0, output_field=IntegerField())
    for field in fields:
        row_length += Coalesce(Length(field), Value(0))
    return Coalesce(Sum(row_length), Value(0))


def _reject_export(
    *,
    user,
    mode: str,
    reason: str,
    session_count: int,
    annotation_count: int | None,
    maximum: int,
) -> None:
    logger.info(
        "Marginalia export rejected by resource limit. "
        "user_id=%s mode=%s reason=%s session_count=%s annotation_count=%s limit=%s",
        user.pk,
        mode,
        reason,
        session_count,
        annotation_count if annotation_count is not None else "not-counted",
        maximum,
    )
    raise ExportTooLargeError(mode=mode, reason=reason, maximum=maximum)
