from __future__ import annotations

import json
import re

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from library.models import BookAuthor
from marginalia.models import (
    HIGHLIGHT_COLOR_YELLOW,
    Annotation,
    ReadingSession,
)
from marginalia.profile import MARGINALIA_PROFILE_URI

from .types import (
    ArchiveAnnotation,
    ArchiveBook,
    ArchiveBookmark,
    ArchiveHighlight,
    ArchiveHighlightBody,
    ArchiveProgress,
    ArchiveReadingSession,
    MarginaliaArchive,
)


ARCHIVE_SCHEMA_VERSION = "0.1.0"
ARCHIVE_TYPE = "SecondPassMarginaliaExport"
DEFAULT_GENERATOR = "Second Pass Library"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ArchiveIntegrityError(ValueError):
    pass


class MissingBookChecksumError(ArchiveIntegrityError):
    def __init__(self):
        super().__init__("A Book is missing a valid SHA-256 checksum.")


class DuplicateBookHashError(ArchiveIntegrityError):
    def __init__(self):
        super().__init__("More than one Book has the same archive file hash.")


def serialize_archive(
    sessions: QuerySet[ReadingSession] | Iterable[ReadingSession],
    *,
    generated_at: datetime,
    include_empty_sessions: bool = False,
    generator: str = DEFAULT_GENERATOR,
) -> MarginaliaArchive:
    materialized = _materialize_sessions(sessions)
    grouped: dict[str, list[tuple[ReadingSession, tuple[Annotation, ...]]]] = (
        defaultdict(list)
    )
    books: dict[str, Any] = {}
    hashes: dict[str, str] = {}

    for session in materialized:
        book_key = str(session.book_id)
        file_hash = _book_file_hash(session.book)
        other_book_key = hashes.get(file_hash)
        if other_book_key is not None and other_book_key != book_key:
            raise DuplicateBookHashError
        hashes[file_hash] = book_key
        annotations = tuple(
            annotation
            for annotation in _session_annotations(session)
            if not annotation.is_deleted
        )
        if not include_empty_sessions and not annotations:
            continue
        books[book_key] = session.book
        grouped[book_key].append((session, annotations))

    archive_books: list[ArchiveBook] = []
    source_session_number = 0
    ordered_books = sorted(books.items(), key=lambda item: _book_file_hash(item[1]))
    for book_key, book in ordered_books:
        archive_sessions: list[ArchiveReadingSession] = []
        for session, annotations in sorted(grouped[book_key], key=_session_sort_key):
            source_session_number += 1
            archive_sessions.append(
                _serialize_session(
                    session,
                    annotations,
                    source_reading_session_id=(
                        f"source-reading-session-{source_session_number:06d}"
                    ),
                )
            )
        archive_books.append(
            ArchiveBook(
                file_hash=_book_file_hash(book),
                title=book.title,
                authors=tuple(_book_authors(book)),
                reading_sessions=tuple(archive_sessions),
            )
        )

    archive = MarginaliaArchive(
        type=ARCHIVE_TYPE,
        schema_version=ARCHIVE_SCHEMA_VERSION,
        profile=MARGINALIA_PROFILE_URI,
        generated_at=_timestamp(generated_at),
        generator=generator,
        books=tuple(archive_books),
    )
    from .validation import validate_archive_value

    validate_archive_value(archive_to_wire(archive))
    return archive


def render_archive_json(archive: MarginaliaArchive) -> bytes:
    from .validation import validate_archive_value

    wire = archive_to_wire(archive)
    validate_archive_value(wire)
    text = json.dumps(
        wire,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        separators=(",", ": "),
    )
    return f"{text}\n".encode("utf-8")


def archive_to_wire(archive: MarginaliaArchive) -> dict[str, Any]:
    return {
        "type": archive.type,
        "schemaVersion": archive.schema_version,
        "profile": archive.profile,
        "generatedAt": archive.generated_at,
        "generator": archive.generator,
        "books": [_book_to_wire(book) for book in archive.books],
    }


def _materialize_sessions(
    sessions: QuerySet[ReadingSession] | Iterable[ReadingSession],
) -> list[ReadingSession]:
    if isinstance(sessions, QuerySet):
        sessions = sessions.select_related("book").prefetch_related(
            Prefetch(
                "annotations",
                queryset=Annotation.objects.filter(is_deleted=False),
                to_attr="_archive_annotations",
            ),
            Prefetch(
                "book__book_authors",
                queryset=BookAuthor.objects.select_related("author").order_by(
                    "position", "id"
                ),
                to_attr="_archive_book_authors",
            ),
        )
    return list(sessions)


def _session_annotations(session: ReadingSession) -> Iterable[Annotation]:
    prefetched = getattr(session, "_archive_annotations", None)
    if prefetched is not None:
        return prefetched
    return session.annotations.filter(is_deleted=False)


def _book_authors(book) -> list[str]:
    links = getattr(book, "_archive_book_authors", None)
    if links is None:
        links = book.book_authors.select_related("author").order_by("position", "id")
    return [link.author.name for link in links]


def _book_file_hash(book) -> str:
    checksum = str(book.checksum or "")
    if not _SHA256_RE.fullmatch(checksum):
        raise MissingBookChecksumError
    return f"sha256:{checksum.lower()}"


def _session_sort_key(item) -> tuple[str, str, str, str, str]:
    session = item[0]
    return (
        session.status,
        _timestamp(session.started_at),
        _timestamp(session.closed_at) if session.closed_at else "",
        _timestamp(session.created_at),
        str(session.pk),
    )


def _annotation_sort_key(annotation: Annotation) -> tuple[int, str, str, str, str]:
    return (
        0 if annotation.location_label else 1,
        annotation.location_label,
        annotation.location,
        _timestamp(annotation.created_at),
        annotation.client_id,
    )


def _serialize_session(
    session: ReadingSession,
    annotations: tuple[Annotation, ...],
    *,
    source_reading_session_id: str,
) -> ArchiveReadingSession:
    return ArchiveReadingSession(
        source_reading_session_id=source_reading_session_id,
        name=session.name,
        notes=session.notes,
        status=session.status,
        started_at=_timestamp(session.started_at),
        closed_at=_timestamp(session.closed_at) if session.closed_at else None,
        created_at=_timestamp(session.created_at),
        updated_at=_timestamp(session.updated_at),
        progress=(
            ArchiveProgress(
                location=session.progress_location,
                location_label=session.progress_location_label or None,
                updated_at=_timestamp(session.progress_updated_at),
            )
            if session.progress_location
            else None
        ),
        annotations=tuple(
            _serialize_annotation(annotation)
            for annotation in sorted(annotations, key=_annotation_sort_key)
        ),
    )


def _serialize_annotation(annotation: Annotation) -> ArchiveAnnotation:
    common = {
        "client_annotation_id": annotation.client_id,
        "location": annotation.location,
        "location_label": annotation.location_label or None,
        "created_at": _timestamp(annotation.created_at),
        "updated_at": _timestamp(annotation.updated_at),
    }
    if annotation.kind == Annotation.KIND_BOOKMARK:
        return ArchiveBookmark(**common)
    return ArchiveHighlight(
        **common,
        body=ArchiveHighlightBody(
            text=annotation.highlight_text,
            prefix=annotation.quote_prefix or None,
            suffix=annotation.quote_suffix or None,
            color=annotation.highlight_color or HIGHLIGHT_COLOR_YELLOW,
            note=annotation.comment_text or None,
        ),
    )


def _book_to_wire(book: ArchiveBook) -> dict[str, Any]:
    value = {
        "title": book.title,
        "authors": list(book.authors),
        "readingSessions": [
            _session_to_wire(session) for session in book.reading_sessions
        ],
    }
    if book.file_hash:
        value["fileHash"] = book.file_hash
    return value


def _session_to_wire(session: ArchiveReadingSession) -> dict[str, Any]:
    progress = session.progress
    return {
        "sourceReadingSessionId": session.source_reading_session_id,
        "name": session.name,
        "notes": session.notes,
        "status": session.status,
        "startedAt": session.started_at,
        "closedAt": session.closed_at,
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
        "progress": (
            _optional_label(
                {
                    "location": progress.location,
                    "updatedAt": progress.updated_at,
                },
                progress.location_label,
            )
            if progress
            else None
        ),
        "annotations": [
            _annotation_to_wire(annotation) for annotation in session.annotations
        ],
    }


def _annotation_to_wire(annotation: ArchiveAnnotation) -> dict[str, Any]:
    payload = {
        "clientAnnotationId": annotation.client_annotation_id,
        "kind": annotation.kind,
        "location": _optional_label(
            {"location": annotation.location}, annotation.location_label
        ),
    }
    if isinstance(annotation, ArchiveHighlight):
        body = {"text": annotation.body.text, "color": annotation.body.color}
        for key, value in (
            ("prefix", annotation.body.prefix),
            ("suffix", annotation.body.suffix),
            ("note", annotation.body.note),
        ):
            if value is not None:
                body[key] = value
        payload["body"] = body
    payload["createdAt"] = annotation.created_at
    payload["updatedAt"] = annotation.updated_at
    return payload


def _optional_label(payload: dict[str, Any], label: str | None) -> dict[str, Any]:
    if label is not None:
        payload["locationLabel"] = label
    return payload


def _timestamp(value: datetime) -> str:
    if timezone.is_naive(value):
        raise ArchiveIntegrityError("Archive timestamps must include a timezone.")
    return value.isoformat().replace("+00:00", "Z")
