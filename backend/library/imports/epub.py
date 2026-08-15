from __future__ import annotations

import logging

from django.core.files.base import ContentFile

from library.cover_services import replace_book_cover
from library.imports.covers import extract_epub_cover, validate_cover_bytes
from library.imports import epub_validation
from library.imports.epub_metadata import read_import_metadata
from library.imports.errors import (
    INVALID_EPUB_MESSAGE,
    InvalidEpubImportError,
    UnsupportedImportSourceError,
    operator_import_detail,
    safe_import_message,
)
from library.imports.opf import ParsedSidecarOpf
from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    ImportItemResult,
)
from library.imports.services import persist_imported_book


EPUB_IMPORT_ERROR_MESSAGE = INVALID_EPUB_MESSAGE
logger = logging.getLogger(__name__)


def import_epub_file(
    file_obj,
    *,
    source_filename: str,
    actor=None,
    sidecar_opf: ParsedSidecarOpf | None = None,
    sidecar_cover_bytes: bytes | None = None,
) -> ImportItemResult:
    """
    Safe item-level import wrapper.

    Normal import/domain failures are converted to failed ImportItemResult rows.
    Unexpected exceptions are also captured here for future batch entrypoints,
    but operator_detail exposes only the exception class for those cases.
    """
    source_label = safe_source_label(source_filename)
    try:
        return _import_epub_file(
            file_obj,
            source_filename=source_filename,
            source_label=source_label,
            actor=actor,
            sidecar_opf=sidecar_opf,
            sidecar_cover_bytes=sidecar_cover_bytes,
        )
    except (InvalidEpubImportError, UnsupportedImportSourceError) as exc:
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=safe_import_message(exc),
            operator_detail=operator_import_detail(exc),
        )
    except Exception as exc:
        logger.error(
            "Unexpected EPUB import failure: source_type=epub exception=%s",
            type(exc).__name__,
        )
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=safe_import_message(exc),
            operator_detail=operator_import_detail(exc),
        )


def safe_source_label(source_filename: str) -> str:
    value = (source_filename or "").replace("\\", "/").strip()
    return value.rsplit("/", 1)[-1] or "unknown.epub"


def _import_epub_file(
    file_obj,
    *,
    source_filename: str,
    source_label: str,
    actor=None,
    sidecar_opf: ParsedSidecarOpf | None = None,
    sidecar_cover_bytes: bytes | None = None,
) -> ImportItemResult:
    source_filename = (source_filename or "").strip()
    if not source_filename.lower().endswith(".epub"):
        raise UnsupportedImportSourceError("Source filename must have .epub extension.")

    data, checksum, file_size = epub_validation.read_file_with_sha256(
        file_obj,
        max_bytes=epub_validation.MAX_EPUB_COMPRESSED_BYTES,
    )
    epub_validation.validate_epub_bytes(data)
    metadata = read_import_metadata(data, sidecar_opf=sidecar_opf)

    persistence_result = persist_imported_book(
        metadata=metadata,
        checksum=checksum,
        file_size=file_size,
        book_file=ContentFile(data, name=source_filename),
        actor=actor,
    )
    if persistence_result.status == IMPORT_STATUS_IMPORTED:
        _attach_import_cover_if_available(
            book=persistence_result.book,
            data=data,
            sidecar_cover_bytes=sidecar_cover_bytes,
        )
    return _item_result_from_persistence_result(
        source_label=source_label,
        status=persistence_result.status,
        book=persistence_result.book,
        message=persistence_result.message,
    )

def _attach_import_cover_if_available(
    *,
    book,
    data: bytes,
    sidecar_cover_bytes: bytes | None = None,
) -> None:
    try:
        cover = (
            validate_cover_bytes(sidecar_cover_bytes)
            if sidecar_cover_bytes is not None
            else None
        )
        if cover is None:
            cover = extract_epub_cover(data)
        if cover is None:
            return
        replace_book_cover(book=book, cover=cover, log_success=False)
    except Exception as exc:
        logger.warning(
            "Optional cover storage failed after successful import: "
            "book=%s exception=%s",
            book.pk,
            type(exc).__name__,
        )


def _item_result_from_persistence_result(
    *,
    source_label: str,
    status: str,
    book,
    message: str,
) -> ImportItemResult:
    if status == IMPORT_STATUS_IMPORTED:
        safe_message = message or "Successfully imported EPUB."
    elif status == IMPORT_STATUS_DUPLICATE:
        safe_message = message or "A book with this checksum already exists."
    elif status == IMPORT_STATUS_CONFLICT:
        safe_message = message or "An identifier from this import already belongs to another book."
    else:
        status = IMPORT_STATUS_FAILED
        safe_message = message or INVALID_EPUB_MESSAGE
    return ImportItemResult(status=status, source_label=source_label, book=book, safe_message=safe_message)
