from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlparse
import zipfile

from defusedxml import ElementTree
from django.core.files.base import ContentFile
from ebooklib import epub

from library.imports.opf import parse_opf_metadata
from library.imports.services import ImportPersistenceResult, persist_imported_book


EPUB_IMPORT_ERROR_MESSAGE = "Invalid or unsupported EPUB file."
READ_CHUNK_BYTES = 1024 * 1024
MAX_CONTAINER_XML_BYTES = 128 * 1024
MAX_PACKAGE_OPF_BYTES = 1024 * 1024


class InvalidEpubImportError(ValueError):
    pass


def import_epub_file(
    file_obj,
    *,
    source_filename: str,
    actor=None,
) -> ImportPersistenceResult:
    source_filename = (source_filename or "").strip()
    if not source_filename.lower().endswith(".epub"):
        raise InvalidEpubImportError("Source filename must have .epub extension.")

    data, checksum, file_size = read_file_with_sha256(file_obj)
    _validate_with_ebooklib(data)
    metadata = _read_import_metadata(data)

    return persist_imported_book(
        metadata=metadata,
        checksum=checksum,
        file_size=file_size,
        source_filename=source_filename,
        book_file=ContentFile(data, name=source_filename),
        actor=actor,
    )


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
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE) from exc


def _read_import_metadata(data: bytes):
    try:
        return parse_opf_metadata(_read_package_opf_xml(data))
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE) from exc


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
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE) from exc


def _read_zip_member_bytes(*, zf: zipfile.ZipFile, member: str, max_bytes: int) -> bytes:
    try:
        info = zf.getinfo(member)
    except KeyError as exc:
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE) from exc

    if info.file_size > max_bytes:
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE)

    with zf.open(info, "r") as fp:
        data = fp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE)
    return data


def _find_package_path(container_xml: bytes) -> str:
    try:
        root = ElementTree.fromstring(container_xml)
    except Exception as exc:
        raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE) from exc

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

    raise InvalidEpubImportError(EPUB_IMPORT_ERROR_MESSAGE)


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
