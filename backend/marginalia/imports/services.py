from __future__ import annotations

from django.utils.dateparse import parse_datetime

from library.queries import visible_books_for_user
from marginalia.archives import MarginaliaArchive, parse_archive
from marginalia.models import ReadingSession

from .staging import create_import_stage


MAX_IMPORT_BYTES = 25 * 1024 * 1024


class ImportPreviewError(ValueError):
    pass


class ImportUploadTooLargeError(ImportPreviewError):
    pass


class NoImportCandidatesError(ImportPreviewError):
    pass


class DuplicateLibraryBookHashError(ImportPreviewError):
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

    matches = _accessible_book_matches(
        user=user,
        file_hashes=[book.file_hash for book, _sessions in surviving_books],
    )
    duplicates = _existing_session_keys(
        user=user, book_ids=[book.pk for book in matches.values()]
    )

    for book_number, (book, sessions) in enumerate(surviving_books, start=1):
        local_book = matches.get(book.file_hash)
        matched = local_book is not None
        matched_book_count += int(matched)
        unmatched_book_count += int(not matched)
        session_rows = []
        for source_session in sessions:
            session_number += 1
            count = len(source_session.annotations)
            annotation_count += count
            possible_duplicate = bool(
                matched and _duplicate_key(local_book.pk, source_session) in duplicates
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
                    {"status": "matched", "book_id": str(local_book.pk)}
                    if matched
                    else {"status": "unmatched"}
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


def _accessible_book_matches(*, user, file_hashes: list[str]):
    checksums = [value.removeprefix("sha256:") for value in file_hashes]
    matches = {}
    for book in visible_books_for_user(user, cached=False).filter(
        checksum__in=checksums
    ):
        file_hash = f"sha256:{book.checksum}"
        if file_hash in matches:
            raise DuplicateLibraryBookHashError
        matches[file_hash] = book
    return matches


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
