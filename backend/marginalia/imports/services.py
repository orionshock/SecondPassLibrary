from __future__ import annotations

import logging
import re
from typing import cast

from django.utils.dateparse import parse_datetime

from core.operational_logging import user_uuid
from library.models import Book
from library.catalog.serializers.books import book_cover_url
from library.queries import visible_books_for_user
from marginalia.archives import MarginaliaArchive, parse_archive
from marginalia.models import ReadingSession

from .staging import create_import_stage


MAX_IMPORT_BYTES = 25 * 1024 * 1024
_SHA256_FILE_HASH_RE = re.compile(r"^sha256:(?P<digest>[0-9a-f]{64})$", re.IGNORECASE)
logger = logging.getLogger(__name__)


class ImportPreviewError(ValueError):
    pass


class ImportUploadTooLargeError(ImportPreviewError):
    pass


class NoImportCandidatesError(ImportPreviewError):
    pass


def preview_import(*, user, file, include_empty_sessions: bool = False) -> dict:
    raw = _read_upload(file)
    archive = parse_archive(raw)
    preview = _build_preview(
        user=user,
        archive=archive,
        include_empty_sessions=include_empty_sessions,
    )
    token, stage = create_import_stage(
        user=user,
        raw=raw,
        include_empty_sessions=include_empty_sessions,
        preview=preview,
    )
    return {
        "import_token": token,
        "include_empty_sessions": stage.include_empty_sessions,
        **preview,
    }


def _read_upload(uploaded_file) -> bytes:
    size = getattr(uploaded_file, "size", None)
    if isinstance(size, int) and size > MAX_IMPORT_BYTES:
        raise ImportUploadTooLargeError
    raw = uploaded_file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ImportUploadTooLargeError
    return raw


def _build_preview(
    *, user, archive: MarginaliaArchive, include_empty_sessions: bool
) -> dict:
    books = []
    session_number = 0
    annotation_count = 0
    matched_book_count = 0
    unmatched_book_count = 0
    unmatched_session_count = 0
    warnings = []

    surviving_books = [
        (
            book,
            tuple(
                session
                for session in book.reading_sessions
                if include_empty_sessions or session.annotations
            ),
        )
        for book in archive.books
    ]
    surviving_books = [
        (book, sessions) for book, sessions in surviving_books if sessions
    ]
    if not surviving_books:
        raise NoImportCandidatesError

    matches = _book_matches(
        user=user,
        file_hashes=[book.file_hash for book, _sessions in surviving_books],
    )
    duplicates = _existing_session_keys(
        user=user,
        book_ids=[
            match["book"].pk
            for match in matches.values()
            if match["status"] == "matched"
        ],
    )

    for book_number, (book, sessions) in enumerate(surviving_books, start=1):
        match = matches.get(book.file_hash, {"status": "unmatched", "reason": "not_found"})
        _log_match_evaluation(
            user=user,
            candidate_number=book_number,
            file_hash=book.file_hash,
            match=match,
        )
        matched_book = (
            cast(Book, match["book"]) if match["status"] == "matched" else None
        )
        matched = matched_book is not None
        matched_book_count += int(matched)
        unmatched_book_count += int(not matched)
        session_rows = []
        for source_session in sessions:
            session_number += 1
            count = len(source_session.annotations)
            annotation_count += count
            possible_duplicate = bool(
                matched_book is not None
                and _duplicate_key(matched_book.pk, source_session) in duplicates
            )
            if possible_duplicate:
                warnings.append(
                    {
                        "code": "POSSIBLE_DUPLICATE_SESSION",
                        "message": "A similar Reading Session already exists.",
                        "candidate_id": f"reading-session-{session_number:06d}",
                    }
                )
            will_import = matched
            if not matched:
                unmatched_session_count += 1
            session_rows.append(
                {
                    "candidate_id": f"reading-session-{session_number:06d}",
                    "source_reading_session_id": source_session.source_reading_session_id,
                    "name": source_session.name,
                    "notes": source_session.notes,
                    "source_status": source_session.status,
                    "will_import_as_status": ReadingSession.STATUS_CLOSED,
                    "started_at": source_session.started_at,
                    "closed_at": source_session.closed_at,
                    "annotation_count": count,
                    "will_import": will_import,
                    "possible_duplicate": possible_duplicate,
                }
            )
        books.append(
            {
                "candidate_id": f"book-{book_number:06d}",
                "file_hash": book.file_hash,
                "title": book.title,
                "authors": list(book.authors),
                "match": (
                    {
                        "status": "matched",
                        "book_id": str(matched_book.pk),
                        "cover_url": book_cover_url(matched_book),
                    }
                    if matched_book is not None
                    else {"status": "unmatched", "reason": match["reason"]}
                ),
                "reading_sessions": session_rows,
            }
        )

    session_count = sum(len(book["reading_sessions"]) for book in books)
    return {
        "can_apply": any(
            session["will_import"]
            for book in books
            for session in book["reading_sessions"]
        ),
        "summary": {
            "book_count": len(books),
            "reading_session_count": session_count,
            "annotation_count": annotation_count,
        },
        "matched_book_count": matched_book_count,
        "unmatched_book_count": unmatched_book_count,
        "unmatched_reading_session_count": unmatched_session_count,
        "unmatched_downloadable_reading_session_count": unmatched_session_count,
        "warnings": warnings,
        "books": books,
    }


def _book_matches(*, user, file_hashes: list[str]) -> dict[str, dict]:
    """Resolve exact EPUB identities without bibliographic metadata fallback."""
    checksums = [value.removeprefix("sha256:") for value in file_hashes]
    accessible: dict[str, list] = {}
    for book in visible_books_for_user(user, cached=False).filter(
        checksum__in=checksums
    ):
        file_hash = f"sha256:{book.checksum}"
        accessible.setdefault(file_hash, []).append(book)

    known_hashes = {
        f"sha256:{checksum}"
        for checksum in Book.objects.filter(checksum__in=checksums).values_list(
            "checksum", flat=True
        )
    }
    matches = {}
    for file_hash in file_hashes:
        visible = accessible.get(file_hash, [])
        match_context = {
            "visible_checksum_matches": len(visible),
            "known_checksum_matches": int(file_hash in known_hashes),
            "metadata_fallback_attempted": False,
        }
        if len(visible) == 1:
            matches[file_hash] = {
                "status": "matched",
                "book": visible[0],
                "matched_by": "checksum",
                **match_context,
            }
        elif len(visible) > 1:
            matches[file_hash] = {
                "status": "unmatched",
                "reason": "ambiguous_match",
                **match_context,
            }
        elif file_hash in known_hashes:
            matches[file_hash] = {
                "status": "unmatched",
                "reason": "book_inaccessible",
                **match_context,
            }
        else:
            matches[file_hash] = {
                "status": "unmatched",
                "reason": "not_found",
                **match_context,
            }
    return matches


def _log_match_evaluation(
    *, user, candidate_number: int, file_hash: str, match: dict
) -> None:
    if match.get("status") == "matched" and match.get("matched_by") == "checksum":
        return
    file_hash_match = _SHA256_FILE_HASH_RE.fullmatch(str(file_hash or "").strip())
    logger.info(
        "Marginalia import Book match evaluated: source_method=web user=%s "
        "candidate=book-%06d "
        "file_hash_present=%s hash_algorithm=%s visible_checksum_matches=%d "
        "known_checksum_matches=%d metadata_fallback_attempted=%s "
        "status=%s outcome=%s",
        user_uuid(user),
        candidate_number,
        str(bool(file_hash)).lower(),
        "sha256" if file_hash_match is not None else "unknown",
        match.get("visible_checksum_matches", 0),
        match.get("known_checksum_matches", 0),
        str(bool(match.get("metadata_fallback_attempted"))).lower(),
        match.get("status", "unmatched"),
        match.get("matched_by") or match.get("reason", "not_found"),
    )


def _existing_session_keys(*, user, book_ids) -> set[tuple]:
    return {
        (book_id, name, started_at)
        for book_id, name, started_at in ReadingSession.objects.filter(
            user=user,
            book_id__in=book_ids,
        ).values_list("book_id", "name", "started_at")
    }


def _duplicate_key(book_id, source_session) -> tuple:
    return (book_id, source_session.name, parse_datetime(source_session.started_at))
