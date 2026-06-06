from __future__ import annotations

from typing import Any

from django.utils import timezone

from core import policies
from library.models import Book, BookIdentifier

from .models import Annotation, ReadingSession, SELECTOR_KIND_EPUB_CFI
from .profile import CURRENT_READING_PROFILE_ID


EXPORT_SCHEMA_VERSION = "0.1.0"
EXPORT_TYPE = "SecondPassMarginaliaExport"
EXPORT_GENERATOR = "Second Pass Library"


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _file_hash(book: Book) -> str:
    book_file = getattr(book, "file", None)
    checksum = getattr(book_file, "checksum", None) if book_file is not None else None
    return f"sha256:{checksum}" if checksum else ""


def _book_source(book: Book) -> str:
    book_file = getattr(book, "file", None)
    checksum = getattr(book_file, "checksum", None) if book_file is not None else None
    return f"book:sha256:{checksum}" if checksum else ""


def _epub_unique_identifier(book: Book) -> str:
    identifiers = getattr(book, "identifiers", None)
    if identifiers is None:
        return ""
    row = identifiers.filter(scheme=BookIdentifier.SCHEME_EPUB_UID).order_by("-is_primary", "value").first()
    return row.value if row is not None else ""


def _book_payload(book: Book) -> dict[str, Any]:
    series = getattr(book, "series", None)
    payload: dict[str, Any] = {
        "title": book.title or "",
        "subtitle": book.subtitle or "",
        "authors": [a.name for a in book.authors.all()],
        "series": getattr(series, "name", "") or "",
        "series_index": str(book.series_index) if book.series_index is not None else None,
        "language": book.language or "",
        "isbn": book.isbn or "",
        "epub_unique_identifier": _epub_unique_identifier(book),
        "sessions": [],
    }
    source = _book_source(book)
    file_hash = _file_hash(book)
    if source:
        payload["source"] = source
    if file_hash:
        payload["file_hash"] = file_hash
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


def _annotation_motivations(annotation: Annotation) -> list[str]:
    if annotation.anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        return [Annotation.MOTIVATION_BOOKMARKING]
    motivations = [Annotation.MOTIVATION_HIGHLIGHTING]
    if (annotation.comment_text or "").strip():
        motivations.append(Annotation.MOTIVATION_COMMENTING)
    return motivations


def _annotation_selector(annotation: Annotation) -> dict[str, Any] | list[dict[str, Any]]:
    fragment: dict[str, Any] = {
        "type": "FragmentSelector",
        "value": annotation.selector_value,
    }
    if annotation.selector_kind != SELECTOR_KIND_EPUB_CFI:
        fragment["type"] = "UnknownSelector"

    if annotation.highlight_text and (annotation.quote_prefix or annotation.quote_suffix):
        quote: dict[str, Any] = {
            "type": "TextQuoteSelector",
            "exact": annotation.highlight_text,
        }
        if annotation.quote_prefix:
            quote["prefix"] = annotation.quote_prefix
        if annotation.quote_suffix:
            quote["suffix"] = annotation.quote_suffix
        return [fragment, quote]
    return fragment


def _annotation_body(annotation: Annotation) -> list[dict[str, Any]]:
    bodies: list[dict[str, Any]] = []
    if annotation.highlight_text or annotation.highlight_color:
        bodies.append(
            {
                "type": "TextualBody",
                "purpose": "describing",
                "value": annotation.highlight_text or "",
                "color": annotation.highlight_color or "yellow",
            }
        )
    if annotation.comment_text:
        bodies.append(
            {
                "type": "TextualBody",
                "purpose": "commenting",
                "value": annotation.comment_text,
            }
        )
    return bodies


def _annotation_payload(annotation: Annotation) -> dict[str, Any]:
    return {
        "motivation": _annotation_motivations(annotation),
        "target": {"selector": _annotation_selector(annotation)},
        "body": _annotation_body(annotation),
        "is_deleted": bool(annotation.is_deleted),
        "created_at": _iso(annotation.created_at),
        "updated_at": _iso(annotation.updated_at),
    }


def _session_payload(session: ReadingSession, export_session_id: str) -> dict[str, Any]:
    annotations = getattr(session, "annotations")
    annotations = [
        _annotation_payload(annotation)
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
        ReadingSession.objects.select_related("book", "book__series", "progress")
        .prefetch_related("book__authors", "book__identifiers", "annotations")
        .filter(user=user, book=book)
        .order_by("started_at", "created_at", "id")
    )


def export_book_marginalia(*, user, book: Book) -> dict[str, Any]:
    if not policies.can_view_book(user=user, book=book):
        raise PermissionError("Book not visible.")

    sessions = list(_sessions_queryset(user=user, book=book))
    payload = _base_export({"type": "book", "book": _book_source(book) or str(book.id)})
    book_payload = _book_payload(book)
    book_payload["sessions"] = [
        _session_payload(session, f"session-{idx}")
        for idx, session in enumerate(sessions, start=1)
    ]
    payload["books"] = [book_payload]
    return payload


def export_session_marginalia(*, user, book: Book, session: ReadingSession) -> dict[str, Any]:
    if session.user_id != getattr(user, "id", None):
        raise PermissionError("Session not owned by user.")
    if session.book_id != book.id:
        raise LookupError("Session does not belong to book.")
    if not policies.can_view_book(user=user, book=book):
        raise PermissionError("Book not visible.")

    session = (
        ReadingSession.objects.select_related("book", "book__series", "progress")
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
