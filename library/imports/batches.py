from __future__ import annotations

from io import BytesIO
import zipfile

from library.imports.archives import (
    ZipImportCandidate,
    plan_zip_import,
    safe_import_source_name,
)
from library.imports.errors import INVALID_ZIP_MESSAGE, operator_import_detail
from library.imports.results import (
    IMPORT_STATUS_FAILED,
    ImportBatchResult,
    ImportItemResult,
)


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
        with zipfile.ZipFile(file_obj, "r") as archive:
            for candidate in plan.candidates:
                batch.items.append(_import_zip_candidate(archive, candidate, actor=actor))
    except Exception as exc:
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

    return import_epub_file(
        BytesIO(data),
        source_filename=candidate.source_name,
        actor=actor,
    )


def _rewind_file(file_obj) -> None:
    seek = getattr(file_obj, "seek", None)
    if callable(seek):
        seek(0)
