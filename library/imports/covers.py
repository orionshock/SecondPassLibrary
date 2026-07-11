from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
from pathlib import PurePosixPath
import posixpath
from urllib.parse import urlparse
import warnings
import zipfile

from defusedxml import ElementTree
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

from library.imports.errors import InvalidEpubImportError
from library.models import Book


MAX_COVER_IMAGE_BYTES = 10 * 1024 * 1024
MAX_COVER_IMAGE_PIXELS = 20_000_000
MAX_CONTAINER_XML_BYTES = 128 * 1024
MAX_PACKAGE_OPF_BYTES = 1024 * 1024

_SUPPORTED_IMAGE_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}
_UNSUPPORTED_COVER_MEDIA_TYPES = {
    "image/svg+xml",
    "image/gif",
}
_URL_SCHEMES = {"http", "https", "data"}


@dataclass(frozen=True)
class ExtractedCover:
    data: bytes
    extension: str


def extract_epub_cover(data: bytes) -> ExtractedCover | None:
    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            package_path = _find_package_path(archive)
            opf_root = _read_opf_root(archive, package_path)
            cover_member = _find_cover_member(opf_root=opf_root, package_path=package_path)
            if cover_member is None:
                return None
            return _read_and_validate_cover(archive=archive, cover_member=cover_member)
    except Exception:
        return None


def attach_cover_to_book(*, book: Book, cover: ExtractedCover | None) -> None:
    if cover is None:
        return
    digest = hashlib.sha256(cover.data).hexdigest()
    book.cover_file.save(f"{digest}{cover.extension}", ContentFile(cover.data), save=True)


def _find_package_path(archive: zipfile.ZipFile) -> str:
    container_xml = _read_zip_member_bytes(
        archive=archive,
        member="META-INF/container.xml",
        max_bytes=MAX_CONTAINER_XML_BYTES,
    )
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
        safe_path = _safe_member_path(full_path)
        if safe_path:
            return safe_path
    raise InvalidEpubImportError()


def _read_opf_root(archive: zipfile.ZipFile, package_path: str):
    opf_xml = _read_zip_member_bytes(
        archive=archive,
        member=package_path,
        max_bytes=MAX_PACKAGE_OPF_BYTES,
    )
    try:
        return ElementTree.fromstring(opf_xml)
    except Exception as exc:
        raise InvalidEpubImportError() from exc


def _find_cover_member(*, opf_root, package_path: str) -> str | None:
    manifest_items = _manifest_items(opf_root)
    cover_item = _find_epub3_cover_item(manifest_items)
    if cover_item is None:
        cover_item = _find_epub2_cover_item(
            opf_root=opf_root,
            manifest_items=manifest_items,
        )
    if cover_item is None:
        return None
    media_type = (cover_item.attrib.get("media-type") or "").strip().lower()
    if media_type in _UNSUPPORTED_COVER_MEDIA_TYPES:
        return None
    href = (cover_item.attrib.get("href") or "").strip()
    return _resolve_manifest_href(package_path=package_path, href=href)


def _manifest_items(opf_root) -> list:
    return [item for item in opf_root.iter() if _local_name(item.tag) == "item"]


def _find_epub3_cover_item(manifest_items: list):
    for item in manifest_items:
        properties = (item.attrib.get("properties") or "").split()
        if "cover-image" in properties:
            return item
    return None


def _find_epub2_cover_item(*, opf_root, manifest_items: list):
    cover_id = ""
    for item in opf_root.iter():
        if _local_name(item.tag) != "meta":
            continue
        if (item.attrib.get("name") or "").strip().casefold() != "cover":
            continue
        cover_id = (item.attrib.get("content") or "").strip()
        break
    if not cover_id:
        return None
    for item in manifest_items:
        if (item.attrib.get("id") or "").strip() == cover_id:
            return item
    return None


def _resolve_manifest_href(*, package_path: str, href: str) -> str | None:
    safe_href = _safe_member_path(href)
    if safe_href is None:
        return None
    base_dir = posixpath.dirname(package_path)
    candidate = posixpath.normpath(posixpath.join(base_dir, safe_href))
    return _safe_member_path(candidate)


def _safe_member_path(path: str) -> str | None:
    value = (path or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ":" in value:
        return None
    if urlparse(value).scheme.lower() in _URL_SCHEMES:
        return None

    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    normalized = str(pure)
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        return None
    return normalized


def _read_and_validate_cover(
    *,
    archive: zipfile.ZipFile,
    cover_member: str,
) -> ExtractedCover | None:
    try:
        info = archive.getinfo(cover_member)
    except KeyError:
        return None
    if info.file_size > MAX_COVER_IMAGE_BYTES:
        return None
    data = _read_zip_member_bytes(
        archive=archive,
        member=cover_member,
        max_bytes=MAX_COVER_IMAGE_BYTES,
    )
    extension = _validated_image_extension(data)
    if extension is None:
        return None
    return ExtractedCover(data=data, extension=extension)


def _validated_image_extension(data: bytes) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            if image.width * image.height > MAX_COVER_IMAGE_PIXELS:
                return None
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning):
        return None
    return _SUPPORTED_IMAGE_FORMATS.get((image.format or "").upper())


def _read_zip_member_bytes(*, archive: zipfile.ZipFile, member: str, max_bytes: int) -> bytes:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise InvalidEpubImportError() from exc
    if info.file_size > max_bytes:
        raise InvalidEpubImportError()
    with archive.open(info, "r") as fp:
        data = fp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidEpubImportError()
    return data


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
