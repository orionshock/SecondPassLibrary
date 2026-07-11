from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlparse
import zipfile

from defusedxml import ElementTree
from django.core.files.base import ContentFile
from ebooklib import epub

from library.imports.errors import (
    INVALID_EPUB_MESSAGE,
    InvalidEpubImportError,
    UnsupportedImportSourceError,
    operator_import_detail,
    safe_import_message,
)
from library.imports.opf import parse_opf_metadata
from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    ImportItemResult,
)
from library.imports.services import persist_imported_book


EPUB_IMPORT_ERROR_MESSAGE = INVALID_EPUB_MESSAGE
READ_CHUNK_BYTES = 1024 * 1024
MAX_CONTAINER_XML_BYTES = 128 * 1024
MAX_PACKAGE_OPF_BYTES = 1024 * 1024


def import_epub_file(
    file_obj,
    *,
    source_filename: str,
    actor=None,
    sidecar_opf_bytes: bytes | None = None,
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
            sidecar_opf_bytes=sidecar_opf_bytes,
        )
    except (InvalidEpubImportError, UnsupportedImportSourceError) as exc:
        return ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=safe_import_message(exc),
            operator_detail=operator_import_detail(exc),
        )
    except Exception as exc:
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
    sidecar_opf_bytes: bytes | None = None,
) -> ImportItemResult:
    source_filename = (source_filename or "").strip()
    if not source_filename.lower().endswith(".epub"):
        raise UnsupportedImportSourceError("Source filename must have .epub extension.")

    data, checksum, file_size = read_file_with_sha256(file_obj)
    _validate_with_ebooklib(data)
    metadata = _read_import_metadata(data, sidecar_opf_bytes=sidecar_opf_bytes)

    persistence_result = persist_imported_book(
        metadata=metadata,
        checksum=checksum,
        file_size=file_size,
        source_filename=source_filename,
        book_file=ContentFile(data, name=source_filename),
        actor=actor,
    )
    return _item_result_from_persistence_result(
        source_label=source_label,
        status=persistence_result.status,
        book=persistence_result.book,
        message=persistence_result.message,
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


def read_file_with_sha256(file_obj, *, chunk_size: int = READ_CHUNK_BYTES) -> tuple[bytes, str, int]:
    digest = hashlib.sha256()
    total_size = 0
    output = BytesIO()

    seek = getattr(file_obj, "seek", None)
    if callable(seek):
        seek(0)

    chunks = getattr(file_obj, "chunks", None)
    if callable(chunks):
        iterator = chunks(chunk_size=chunk_size)
    else:
        iterator = iter(lambda: file_obj.read(chunk_size), b"")

    for chunk in iterator:
        if not chunk:
            continue
        digest.update(chunk)
        total_size += len(chunk)
        output.write(chunk)

    if callable(seek):
        seek(0)

    return output.getvalue(), digest.hexdigest(), total_size


def _validate_with_ebooklib(data: bytes) -> None:
    try:
        epub.read_epub(BytesIO(data), options={"ignore_ncx": True})
    except Exception as exc:
        raise InvalidEpubImportError() from exc


def _read_import_metadata(data: bytes, *, sidecar_opf_bytes: bytes | None = None):
    try:
        epub_metadata = parse_opf_metadata(_read_package_opf_xml(data))
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError() from exc
    if not sidecar_opf_bytes:
        return epub_metadata
    return _read_sidecar_metadata_or_fallback(
        sidecar_opf_bytes=sidecar_opf_bytes,
        fallback_metadata=epub_metadata,
    )


def _read_sidecar_metadata_or_fallback(*, sidecar_opf_bytes: bytes, fallback_metadata):
    try:
        sidecar_metadata = parse_opf_metadata(sidecar_opf_bytes)
    except Exception:
        return fallback_metadata
    if not _sidecar_has_real_title(sidecar_metadata):
        return fallback_metadata
    return sidecar_metadata


def _sidecar_has_real_title(metadata) -> bool:
    title = metadata.title.strip()
    return bool(title) and title.casefold() != "untitled"


def _read_package_opf_xml(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(BytesIO(data), "r") as zf:
            container_xml = _read_zip_member_bytes(
                zf=zf,
                member="META-INF/container.xml",
                max_bytes=MAX_CONTAINER_XML_BYTES,
            )
            package_path = _find_package_path(container_xml)
            return _read_zip_member_bytes(
                zf=zf,
                member=package_path,
                max_bytes=MAX_PACKAGE_OPF_BYTES,
            )
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError() from exc


def _read_zip_member_bytes(*, zf: zipfile.ZipFile, member: str, max_bytes: int) -> bytes:
    try:
        info = zf.getinfo(member)
    except KeyError as exc:
        raise InvalidEpubImportError() from exc

    if info.file_size > max_bytes:
        raise InvalidEpubImportError()

    with zf.open(info, "r") as fp:
        data = fp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidEpubImportError()
    return data


def _find_package_path(container_xml: bytes) -> str:
    try:
        root = ElementTree.fromstring(container_xml)
    except Exception as exc:
        raise InvalidEpubImportError() from exc

    for item in root.iter():
        if _local_name(item.tag) != "rootfile":
            continue
        media_type = (item.attrib.get("media-type") or "").strip()
        full_path = (item.attrib.get("full-path") or "").strip()
        if media_type and media_type != "application/oebps-package+xml":
            continue
        safe_path = _safe_posix_relpath(full_path)
        if safe_path:
            return safe_path

    raise InvalidEpubImportError()


def _safe_posix_relpath(path: str) -> str | None:
    value = (path or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ":" in value:
        return None
    if urlparse(value).scheme.lower() in {"http", "https", "data"}:
        return None

    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None

    normalized = str(pure)
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        return None
    return normalized


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
