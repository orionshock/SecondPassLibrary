from __future__ import annotations

from io import BytesIO
import logging
import zipfile

from library.imports.archives import (
    MAX_OPF_SIDECAR_XML_BYTES,
    ZipImportCandidate,
    ZipMember,
    plan_zip_import,
    resolve_zip_member_reference,
    safe_import_source_name,
)
from library.imports.covers import MAX_COVER_IMAGE_BYTES
from library.imports.errors import INVALID_ZIP_MESSAGE, operator_import_detail
from library.imports.opf import ParsedSidecarOpf, parse_sidecar_opf
from library.imports.results import (
    IMPORT_STATUS_FAILED,
    ImportBatchResult,
    ImportItemResult,
)
from library.queries import defer_visible_books_cache_invalidation


logger = logging.getLogger(__name__)


def import_zip_file(
    file_obj,
    *,
    source_filename: str,
    actor=None,
) -> ImportBatchResult:
    source_label = safe_import_source_name(source_filename)
    _rewind_file(file_obj)
    plan = plan_zip_import(file_obj, source_label=source_label)
    batch = ImportBatchResult(
        source_type="zip",
        source_label=source_label,
        items=list(plan.item_results),
        discovered_count=plan.discovered_count,
    )
    if not plan.candidates:
        return batch

    _rewind_file(file_obj)
    try:
        with defer_visible_books_cache_invalidation(), zipfile.ZipFile(file_obj, "r") as archive:
            for candidate in plan.candidates:
                batch.items.append(
                    _import_zip_candidate(
                        archive,
                        candidate,
                        members_index=plan.members_index,
                        actor=actor,
                    )
                )
    except Exception as exc:
        logger.error(
            "Unexpected ZIP batch failure: source_type=zip "
            "completion_state=partial exception=%s",
            type(exc).__name__,
        )
        batch.items.append(
            ImportItemResult(
                status=IMPORT_STATUS_FAILED,
                source_label=source_label,
                safe_message=INVALID_ZIP_MESSAGE,
                operator_detail=operator_import_detail(exc),
            )
        )
    return batch


def _import_zip_candidate(
    archive: zipfile.ZipFile,
    candidate: ZipImportCandidate,
    *,
    members_index: dict[str, ZipMember],
    actor=None,
) -> ImportItemResult:
    from library.imports.epub import import_epub_file

    try:
        with archive.open(candidate.archive_name or candidate.safe_name, "r") as fp:
            data = fp.read(candidate.file_size + 1)
    except Exception as exc:
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=candidate.source_label,
            safe_message=INVALID_ZIP_MESSAGE,
            operator_detail=operator_import_detail(exc),
        )

    if len(data) != candidate.file_size:
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=candidate.source_label,
            safe_message=INVALID_ZIP_MESSAGE,
        )

    sidecar_opf = _read_sidecar_opf(archive, candidate)
    return import_epub_file(
        BytesIO(data),
        source_filename=candidate.source_name,
        actor=actor,
        sidecar_opf=sidecar_opf,
        sidecar_cover_bytes=_read_sidecar_cover_bytes(
            archive,
            candidate=candidate,
            sidecar_opf=sidecar_opf,
            members_index=members_index,
        ),
    )


def _read_sidecar_opf(
    archive: zipfile.ZipFile,
    candidate: ZipImportCandidate,
) -> ParsedSidecarOpf | None:
    if not candidate.sidecar_opf_name:
        return None

    try:
        with archive.open(candidate.sidecar_archive_name or candidate.sidecar_opf_name, "r") as fp:
            data = fp.read(MAX_OPF_SIDECAR_XML_BYTES + 1)
    except Exception:
        return None

    if len(data) > MAX_OPF_SIDECAR_XML_BYTES:
        return None
    try:
        return parse_sidecar_opf(data)
    except Exception:
        return None


def _read_sidecar_cover_bytes(
    archive: zipfile.ZipFile,
    *,
    candidate: ZipImportCandidate,
    sidecar_opf: ParsedSidecarOpf | None,
    members_index: dict[str, ZipMember],
) -> bytes | None:
    if sidecar_opf is None or not sidecar_opf.cover_href:
        return None
    member = resolve_zip_member_reference(
        base_member=candidate.sidecar_opf_name or "",
        href=sidecar_opf.cover_href,
        members_index=members_index,
    )
    if member is None or member.file_size > MAX_COVER_IMAGE_BYTES:
        return None
    try:
        with archive.open(member.archive_name or member.safe_name, "r") as fp:
            data = fp.read(MAX_COVER_IMAGE_BYTES + 1)
    except Exception:
        return None
    if len(data) != member.file_size or len(data) > MAX_COVER_IMAGE_BYTES:
        return None
    return data


def _rewind_file(file_obj) -> None:
    seek = getattr(file_obj, "seek", None)
    if callable(seek):
        seek(0)
