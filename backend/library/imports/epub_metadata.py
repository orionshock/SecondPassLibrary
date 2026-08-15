from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse
import zipfile

from defusedxml import ElementTree

from library.imports.errors import InvalidEpubImportError
from library.imports.opf import ParsedSidecarOpf, parse_opf_metadata


MAX_CONTAINER_XML_BYTES = 128 * 1024
MAX_PACKAGE_OPF_BYTES = 1024 * 1024


def read_import_metadata(data: bytes, *, sidecar_opf: ParsedSidecarOpf | None = None):
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

