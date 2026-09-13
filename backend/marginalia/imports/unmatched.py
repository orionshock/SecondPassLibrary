from __future__ import annotations

import logging
import re
import unicodedata

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from marginalia.archives import (
    ArchiveBook,
    ArchiveValidationError,
    MalformedArchiveError,
    MarginaliaArchive,
    UnsupportedArchiveProfileError,
    parse_archive,
    render_archive_json,
)

from .plan import StagedImportPlan, StagedImportPlanError
from .staging import read_import_stage, read_staged_archive


logger = logging.getLogger(__name__)
ZIP_FILENAME = "secondpass-marginalia-sessions.zip"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_RESERVED_KEYS = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class NoDownloadableUnmatchedSessionsError(Exception):
    pass


class UnmatchedStageIntegrityError(Exception):
    pass


class UnmatchedZipAssemblyError(Exception):
    pass


def unmatched_archive_zip(*, user, import_token: str) -> bytes:
    stage = read_import_stage(user=user, token=import_token)
    try:
        plan = StagedImportPlan.decode(stage.preview)
        archive = parse_archive(read_staged_archive(stage))
        books = plan.unmatched_archive_books(
            archive=archive,
            include_empty_sessions=stage.include_empty_sessions,
        )
    except (
        ArchiveValidationError,
        MalformedArchiveError,
        StagedImportPlanError,
        UnsupportedArchiveProfileError,
    ) as exc:
        logger.error("Marginalia unmatched download found inconsistent staged data.")
        raise UnmatchedStageIntegrityError from exc

    if not books:
        raise NoDownloadableUnmatchedSessionsError
    try:
        return _render_zip(archive=archive, books=books)
    except Exception as exc:
        logger.error("Marginalia unmatched ZIP assembly failed.")
        raise UnmatchedZipAssemblyError from exc


def _render_zip(
    *, archive: MarginaliaArchive, books: tuple[tuple[ArchiveBook, tuple], ...]
) -> bytes:
    output = BytesIO()
    used_book_keys: set[str] = set()
    with ZipFile(
        output,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as zip_file:
        for book_number, (book, sessions) in enumerate(books, start=1):
            book_key = _safe_key(
                book.title,
                fallback=f"book-{book_number}",
                used=used_book_keys,
            )
            directory = f"{book_number:02d}-{book_key}"
            used_session_keys: set[str] = set()
            for session_number, session in enumerate(sessions, start=1):
                session_key = _safe_key(
                    session.source_reading_session_id or session.started_at,
                    fallback=f"session-{session_number}",
                    used=used_session_keys,
                )
                member_name = (
                    f"{directory}/{book_number:02d}-{session_number:02d}-"
                    f"{book_key}-{session_key}.json"
                )
                mini_archive = MarginaliaArchive(
                    type=archive.type,
                    schema_version=archive.schema_version,
                    profile=archive.profile,
                    generated_at=archive.generated_at,
                    generator=archive.generator,
                    books=(
                        ArchiveBook(
                            file_hash=book.file_hash,
                            title=book.title,
                            authors=book.authors,
                            reading_sessions=(session,),
                        ),
                    ),
                )
                info = ZipInfo(member_name, date_time=_FIXED_ZIP_TIME)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o600 << 16
                zip_file.writestr(
                    info,
                    render_archive_json(mini_archive),
                    compress_type=ZIP_DEFLATED,
                    compresslevel=9,
                )
    return output.getvalue()


def _safe_key(value: object, *, fallback: str, used: set[str]) -> str:
    text = str(value or "").strip()
    ascii_value = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    base = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    base = base[:60].rstrip("-") or fallback
    if base in _RESERVED_KEYS:
        base = f"item-{base}"
    key = base
    suffix = 2
    while key in used:
        marker = f"-{suffix}"
        key = f"{base[: 60 - len(marker)].rstrip('-')}{marker}"
        suffix += 1
    used.add(key)
    return key
