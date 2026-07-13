from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.utils import timezone

from core.operational_logging import info_on_commit, user_uuid
from library.models import Book, BookIdentifier

from ..profile.marginalia import profile_annotation_from_model
from ..models import ReadingSession
from ..profile.validation import CURRENT_READING_PROFILE_ID


EXPORT_SCHEMA_VERSION = "0.1.0"
EXPORT_TYPE = "SecondPassMarginaliaExport"
EXPORT_GENERATOR = "Second Pass Library"
logger = logging.getLogger(__name__)


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _file_hash(book: Book) -> str:
    checksum = getattr(book, "checksum", None)
    return f"sha256:{checksum}" if checksum else ""


def _book_source(book: Book) -> str:
    checksum = getattr(book, "checksum", None)
    return f"book:sha256:{checksum}" if checksum else ""


def _epub_unique_identifier(book: Book) -> str:
    identifiers = getattr(book, "identifiers", None)
    if identifiers is None:
        return ""
    row = (
        identifiers.filter(scheme=BookIdentifier.SCHEME_EPUB_UID)
        .order_by("normalized_value", "value")
        .first()
    )
    return row.value if row is not None else ""


def _isbn(book: Book) -> str:
    identifiers = getattr(book, "identifiers", None)
    if identifiers is None:
        return ""
    row = (
        identifiers.filter(
            scheme__in=[BookIdentifier.SCHEME_ISBN_13, BookIdentifier.SCHEME_ISBN_10]
        )
        .order_by("scheme", "normalized_value", "value")
        .first()
    )
    return row.value if row is not None else ""


def _book_series_link(book: Book):
    try:
        return book.book_series
    except Book.book_series.RelatedObjectDoesNotExist:
        return None


def _format_series_index(value) -> str | None:
    if value is None:
        return None
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0")
        if formatted.endswith("."):
            formatted += "0"
    return formatted


def _book_payload(book: Book) -> dict[str, Any]:
    series_link = _book_series_link(book)
    series = series_link.series if series_link is not None else None
    source = _book_source(book)
    file_hash = _file_hash(book)
    payload: dict[str, Any] = {
        "title": book.title or "",
        "subtitle": book.subtitle or "",
        "authors": [a.name for a in book.authors.all()],
        "series": getattr(series, "name", "") or "",
        "series_index": (
            _format_series_index(series_link.series_index)
            if series_link is not None
            else None
        ),
        "language": book.language or "",
        "isbn": _isbn(book),
        "epub_unique_identifier": _epub_unique_identifier(book),
    }
    if source:
        payload["source"] = source
    if file_hash:
        payload["file_hash"] = file_hash
    payload["sessions"] = []
    return payload


def _progress_payload(session: ReadingSession) -> dict[str, Any] | None:
    progress = getattr(session, "progress", None)
    if progress is None:
        return None
    return {
        "current_location": progress.current_location or {},
        "progression": progress.progression,
        "profile_version": progress.profile_version,
        "updated_at": _iso(progress.updated_at),
    }


def _session_payload(session: ReadingSession, export_session_id: str) -> dict[str, Any]:
    annotations = getattr(session, "annotations")
    annotations = [
        profile_annotation_from_model(annotation)
        for annotation in annotations.all()
        if not annotation.is_deleted
    ]
    return {
        "export_session_id": export_session_id,
        "name": session.name or "",
        "status": session.status,
        "started_at": _iso(session.started_at),
        "completed_at": _iso(session.completed_at),
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
        "notes": session.notes or "",
        "progress": _progress_payload(session),
        "annotations": annotations,
    }


def _base_export(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": EXPORT_TYPE,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "profile": CURRENT_READING_PROFILE_ID,
        "generated_at": timezone.now().isoformat(),
        "generator": EXPORT_GENERATOR,
        "scope": scope,
        "books": [],
    }


def _sessions_queryset(*, user, book: Book):
    return (
        ReadingSession.objects.select_related(
            "book", "book__book_series", "book__book_series__series", "progress"
        )
        .prefetch_related("book__authors", "book__identifiers", "annotations")
        .filter(user=user, book=book)
        .order_by("started_at", "created_at", "id")
    )


def selected_book_sessions(*, user, book: Book, session_ids) -> list[ReadingSession]:
    unique_ids = list(dict.fromkeys(UUID(str(session_id)) for session_id in session_ids))
    sessions = list(_sessions_queryset(user=user, book=book).filter(id__in=unique_ids))
    sessions_by_id = {session.id: session for session in sessions}
    if len(sessions_by_id) != len(unique_ids):
        raise LookupError("One or more sessions were not found.")
    return [sessions_by_id[session_id] for session_id in unique_ids]


def _book_payload_with_sessions(book: Book, sessions: list[ReadingSession]) -> dict[str, Any]:
    book_payload = _book_payload(book)
    book_payload["sessions"] = [
        _session_payload(session, f"session-{idx}")
        for idx, session in enumerate(sessions, start=1)
    ]
    return book_payload


def export_selected_marginalia(*, user, selection: list[dict[str, Any]]) -> dict[str, Any]:
    scope_books: list[dict[str, str]] = []
    payload = _base_export({"type": "selected", "books": scope_books})

    for item in selection:
        book = item["book"]
        sessions = item["sessions"]
        if sessions == "all":
            resolved_sessions = list(_sessions_queryset(user=user, book=book))
            session_filter = "all"
        else:
            resolved_sessions = list(sessions)
            session_filter = "selected"
        scope_books.append(
            {
                "book": _book_source(book) or str(book.id),
                "session_filter": session_filter,
            }
        )
        payload["books"].append(_book_payload_with_sessions(book, resolved_sessions))

    _log_export_completed(user=user, scope_type="selected", payload=payload)
    return payload


def export_book_marginalia(
    *, user, book: Book, sessions: list[ReadingSession] | None = None, selected: bool = False
) -> dict[str, Any]:
    if sessions is None:
        sessions = list(_sessions_queryset(user=user, book=book))

    scope = {"type": "book", "book": _book_source(book) or str(book.id)}
    if selected:
        scope["session_filter"] = "selected"
    payload = _base_export(scope)
    payload["books"] = [_book_payload_with_sessions(book, sessions)]
    return payload


def export_all_marginalia(*, user) -> dict[str, Any]:
    payload = _base_export({"type": "all"})
    sessions = (
        ReadingSession.objects.select_related(
            "book", "book__book_series", "book__book_series__series", "progress"
        )
        .prefetch_related(
            "book__authors",
            "book__identifiers",
            "book__group_assignments__group__memberships",
            "annotations",
        )
        .filter(user=user)
        .order_by("book__title", "book_id", "started_at", "created_at", "id")
    )

    books_by_id: dict[str, dict[str, Any]] = {}
    session_counts: dict[str, int] = {}
    for session in sessions:
        book = session.book
        book_key = str(book.id)
        if book_key not in books_by_id:
            books_by_id[book_key] = _book_payload(book)
            payload["books"].append(books_by_id[book_key])
            session_counts[book_key] = 0

        session_counts[book_key] += 1
        books_by_id[book_key]["sessions"].append(
            _session_payload(session, f"session-{session_counts[book_key]}")
        )

    _log_export_completed(user=user, scope_type="all", payload=payload)
    return payload


def export_session_marginalia(*, user, book: Book, session: ReadingSession) -> dict[str, Any]:
    if session.user_id != getattr(user, "id", None):
        raise PermissionError("Session not owned by user.")
    if session.book_id != book.id:
        raise LookupError("Session does not belong to book.")

    session = (
        ReadingSession.objects.select_related(
            "book", "book__book_series", "book__book_series__series", "progress"
        )
        .prefetch_related("book__authors", "book__identifiers", "annotations")
        .get(pk=session.pk)
    )

    payload = _base_export(
        {
            "type": "session",
            "book": _book_source(book) or str(book.id),
            "session": "session-1",
        }
    )
    book_payload = _book_payload(book)
    book_payload["sessions"] = [_session_payload(session, "session-1")]
    payload["books"] = [book_payload]
    return payload


def _log_export_completed(*, user, scope_type: str, payload: dict[str, Any]) -> None:
    books = payload.get("books") or []
    session_count = 0
    annotation_count = 0
    for book in books:
        sessions = book.get("sessions") or []
        session_count += len(sessions)
        annotation_count += sum(len(session.get("annotations") or []) for session in sessions)
    info_on_commit(
        logger,
        "Marginalia export completed: user=%s scope=%s books=%d sessions=%d annotations=%d",
        user_uuid(user),
        scope_type,
        len(books),
        session_count,
        annotation_count,
    )
