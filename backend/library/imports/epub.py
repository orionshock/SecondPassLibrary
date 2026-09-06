from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile

from library.catalog.names import AmbiguousCatalogEntityName
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
    source_label: str | None = None,
    source_method: str = "web",
    archive_limits: epub_validation.EpubArchiveLimits | None = None,
    candidate_ordinal: int | None = None,
) -> ImportItemResult:
    """
    Safe item-level import wrapper.

    Normal import/domain failures are converted to failed ImportItemResult rows.
    Unexpected exceptions are also captured here for future batch entrypoints,
    but operator_detail exposes only the exception class for those cases.
    """
    source_label = source_label or safe_source_label(source_filename)
    logger.info("Import candidate received: source_method=%s", source_method)
    try:
        result = _import_epub_file(
            file_obj,
            source_filename=source_filename,
            source_label=source_label,
            actor=actor,
            sidecar_opf=sidecar_opf,
            sidecar_cover_bytes=sidecar_cover_bytes,
            archive_limits=archive_limits,
            source_method=source_method,
            candidate_ordinal=candidate_ordinal,
        )
    except (InvalidEpubImportError, UnsupportedImportSourceError, DjangoValidationError) as exc:
        result = ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=(
                INVALID_EPUB_MESSAGE
                if isinstance(exc, DjangoValidationError)
                else safe_import_message(exc)
            ),
            operator_detail=operator_import_detail(exc),
            error_category="invalid_candidate",
        )
        logger.warning(
            "EPUB import rejected: source_method=%s source=%s "
            "category=invalid_candidate transaction=not_started_or_rolled_back "
            "storage_cleanup=handled_if_needed retryable=false exception=%s",
            source_method,
            _bounded_log_source(source_label),
            type(exc).__name__,
        )
    except Exception as exc:
        error_category = "io_error" if isinstance(exc, OSError) else "unexpected"
        logger.error(
            "Unexpected EPUB import failure: source_method=%s source=%s "
            "category=%s transaction=not_started_or_rolled_back "
            "storage_cleanup=handled_if_needed retryable=%s exception=%s",
            source_method,
            _bounded_log_source(source_label),
            error_category,
            str(isinstance(exc, OSError)).lower(),
            type(exc).__name__,
        )
        result = ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=safe_import_message(exc),
            operator_detail=operator_import_detail(exc),
            error_category=error_category,
        )
    logger.info(
        "Import candidate completed: source_method=%s status=%s book=%s",
        source_method,
        result.status,
        getattr(result.book, "pk", "none"),
    )
    return result


def safe_source_label(source_filename: str) -> str:
    value = (source_filename or "").replace("\\", "/").strip()
    return value.rsplit("/", 1)[-1] or "unknown.epub"


def _bounded_log_source(source_label: str) -> str:
    value = safe_source_label(source_label).replace("\r", " ").replace("\n", " ")
    return value[:160]


def _import_epub_file(
    file_obj,
    *,
    source_filename: str,
    source_label: str,
    actor=None,
    sidecar_opf: ParsedSidecarOpf | None = None,
    sidecar_cover_bytes: bytes | None = None,
    archive_limits: epub_validation.EpubArchiveLimits | None = None,
    source_method: str,
    candidate_ordinal: int | None = None,
) -> ImportItemResult:
    source_filename = (source_filename or "").strip()
    if not source_filename.lower().endswith(".epub"):
        raise UnsupportedImportSourceError("Source filename must have .epub extension.")

    data, checksum, file_size = epub_validation.read_file_with_sha256(
        file_obj,
        max_bytes=(
            archive_limits.compressed_bytes
            if archive_limits is not None
            else epub_validation.MAX_EPUB_COMPRESSED_BYTES
        ),
    )
    epub_validation.validate_epub_bytes(data, limits=archive_limits)
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
    if persistence_result.ambiguity is not None:
        _log_ambiguous_identity_conflict(
            ambiguity=persistence_result.ambiguity,
            source_method=source_method,
            source_label=source_label,
            candidate_ordinal=candidate_ordinal,
        )
    return _item_result_from_persistence_result(
        source_label=source_label,
        status=persistence_result.status,
        book=persistence_result.book,
        message=persistence_result.message,
        persistence_error_category=persistence_result.error_category,
        title=metadata.title,
        authors=tuple(author.name for author in metadata.authors),
    )


def _log_ambiguous_identity_conflict(
    *,
    ambiguity: AmbiguousCatalogEntityName,
    source_method: str,
    source_label: str,
    candidate_ordinal: int | None,
) -> None:
    logger.warning(
        "Import relationship identity conflict: source_method=%s source=%s "
        "candidate_ordinal=%s category=%s entity_type=%s incoming_name=%s "
        "normalized_name=%s match_count=%d matched_ids=%s "
        "candidate_persisted=false resolution=operator_cleanup_required",
        source_method,
        _bounded_log_source(source_label),
        candidate_ordinal if candidate_ordinal is not None else "unavailable",
        f"{ambiguity.kind.casefold()}_ambiguous",
        ambiguity.kind,
        ambiguity.display_name,
        ambiguity.normalized_name,
        ambiguity.match_count,
        ",".join(ambiguity.matched_ids),
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
    persistence_error_category: str,
    title: str,
    authors: tuple[str, ...],
) -> ImportItemResult:
    if status == IMPORT_STATUS_IMPORTED:
        safe_message = message or "Successfully imported EPUB."
        error_category = ""
    elif status == IMPORT_STATUS_DUPLICATE:
        safe_message = message or (
            "This exact EPUB file is already in the library. "
            "No action is needed unless you intended to import a different file."
        )
        error_category = "checksum_duplicate"
    elif status == IMPORT_STATUS_CONFLICT:
        safe_message = message or (
            "Catalog metadata matches multiple existing records. "
            "Review the Author and Series metadata, then retry the import."
        )
        error_category = persistence_error_category or "catalog_identity_conflict"
    else:
        status = IMPORT_STATUS_FAILED
        safe_message = message or INVALID_EPUB_MESSAGE
        error_category = "persistence_failure"
    return ImportItemResult(
        status=status,
        source_label=source_label,
        book=book,
        safe_message=safe_message,
        title=title,
        authors=authors,
        error_category=error_category,
    )
