from __future__ import annotations

from io import BytesIO
import hashlib
import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse
import zipfile

from defusedxml import ElementTree
from django.core.files.base import ContentFile
from ebooklib import epub

from library.cover_services import replace_book_cover
from library.imports.archives import safe_zip_member_name
from library.imports.errors import (
    INVALID_EPUB_MESSAGE,
    InvalidEpubImportError,
    UnsupportedImportSourceError,
    operator_import_detail,
    safe_import_message,
)
from library.imports.covers import extract_epub_cover, validate_cover_bytes
from library.imports.opf import ParsedSidecarOpf, parse_opf_metadata
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
# EPUBs are compressed application archives. These limits are deliberately
# below the 1 GiB outer import-upload ceiling and align with the 200 MiB batch
# EPUB-member limit. They bound work before EbookLib parses any archive data.
MAX_EPUB_COMPRESSED_BYTES = 200 * 1024 * 1024
MAX_EPUB_MEMBERS = 2000
MAX_EPUB_MEMBER_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_EPUB_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_EPUB_MEMBER_COMPRESSION_RATIO = 100
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

    data, checksum, file_size = read_file_with_sha256(
        file_obj,
        max_bytes=MAX_EPUB_COMPRESSED_BYTES,
    )
    validate_epub_bytes(data)
    metadata = _read_import_metadata(data, sidecar_opf=sidecar_opf)

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


def read_file_with_sha256(
    file_obj,
    *,
    chunk_size: int = READ_CHUNK_BYTES,
    max_bytes: int | None = None,
) -> tuple[bytes, str, int]:
    if isinstance(file_obj, bytes):
        if max_bytes is not None and len(file_obj) > max_bytes:
            raise InvalidEpubImportError()
        return file_obj, hashlib.sha256(file_obj).hexdigest(), len(file_obj)

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
        if max_bytes is not None and total_size > max_bytes:
            raise InvalidEpubImportError()
        output.write(chunk)

    if callable(seek):
        seek(0)

    return output.getvalue(), digest.hexdigest(), total_size


def validate_epub_bytes(data: bytes) -> None:
    validate_epub_archive(data)
    try:
        epub.read_epub(BytesIO(data), options={"ignore_ncx": True})
    except Exception as exc:
        raise InvalidEpubImportError() from exc


def validate_epub_archive(
    data: bytes,
    *,
    max_compressed_bytes: int | None = None,
    max_members: int | None = None,
    max_member_uncompressed_bytes: int | None = None,
    max_total_uncompressed_bytes: int | None = None,
    max_member_compression_ratio: int | None = None,
) -> None:
    """Validate an EPUB ZIP central directory without extracting members."""
    max_compressed_bytes = (
        MAX_EPUB_COMPRESSED_BYTES if max_compressed_bytes is None else max_compressed_bytes
    )
    max_members = MAX_EPUB_MEMBERS if max_members is None else max_members
    max_member_uncompressed_bytes = (
        MAX_EPUB_MEMBER_UNCOMPRESSED_BYTES
        if max_member_uncompressed_bytes is None
        else max_member_uncompressed_bytes
    )
    max_total_uncompressed_bytes = (
        MAX_EPUB_TOTAL_UNCOMPRESSED_BYTES
        if max_total_uncompressed_bytes is None
        else max_total_uncompressed_bytes
    )
    max_member_compression_ratio = (
        MAX_EPUB_MEMBER_COMPRESSION_RATIO
        if max_member_compression_ratio is None
        else max_member_compression_ratio
    )

    if len(data) > max_compressed_bytes:
        raise InvalidEpubImportError()

    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            infos = archive.infolist()
    except Exception as exc:
        raise InvalidEpubImportError() from exc

    if len(infos) > max_members:
        raise InvalidEpubImportError()

    normalized_names: set[str] = set()
    total_uncompressed_bytes = 0
    for info in infos:
        normalized_name = _safe_epub_member_name(info)
        if normalized_name is None or normalized_name in normalized_names:
            raise InvalidEpubImportError()
        normalized_names.add(normalized_name)

        if info.flag_bits & 0x1:
            raise InvalidEpubImportError()
        if info.file_size > max_member_uncompressed_bytes:
            raise InvalidEpubImportError()

        total_uncompressed_bytes += info.file_size
        if total_uncompressed_bytes > max_total_uncompressed_bytes:
            raise InvalidEpubImportError()

        if info.file_size and (
            info.compress_size == 0
            or info.file_size > info.compress_size * max_member_compression_ratio
        ):
            raise InvalidEpubImportError()


def _safe_epub_member_name(info: zipfile.ZipInfo) -> str | None:
    # Python normalizes backslashes in ``filename`` while preserving the raw
    # central-directory value in ``orig_filename``.
    archive_name = info.orig_filename
    if "\\" in archive_name:
        return None

    # Directory entries conventionally end in '/'; validate their path using
    # the same rules as file members. A file and directory with the same
    # normalized path are a collision too.
    name = archive_name[:-1] if info.is_dir() and archive_name.endswith("/") else archive_name
    safe_name = safe_zip_member_name(name)
    if safe_name is None:
        return None
    return safe_name


def _read_import_metadata(data: bytes, *, sidecar_opf: ParsedSidecarOpf | None = None):
    try:
        epub_metadata = parse_opf_metadata(_read_package_opf_xml(data))
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError() from exc
    if sidecar_opf is None:
        return epub_metadata
    return _read_sidecar_metadata_or_fallback(
        sidecar_metadata=sidecar_opf.metadata,
        fallback_metadata=epub_metadata,
    )


def _read_sidecar_metadata_or_fallback(*, sidecar_metadata, fallback_metadata):
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
