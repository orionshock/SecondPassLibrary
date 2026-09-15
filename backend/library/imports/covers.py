from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import warnings

from defusedxml import ElementTree
from PIL import Image, UnidentifiedImageError

from library.cover_objects import cover_extension_for_image_format
from library.imports.epub_package import EpubPackage, open_epub_package


MAX_COVER_IMAGE_BYTES = 10 * 1024 * 1024
MAX_COVER_IMAGE_PIXELS = 20_000_000

_UNSUPPORTED_COVER_MEDIA_TYPES = {
    "image/svg+xml",
    "image/gif",
}


@dataclass(frozen=True)
class ExtractedCover:
    data: bytes
    extension: str


def extract_epub_cover(data: bytes) -> ExtractedCover | None:
    try:
        with open_epub_package(data) as package:
            opf_root = ElementTree.fromstring(package.read_package_document())
            cover_member = _find_cover_member(opf_root=opf_root, package=package)
            if cover_member is None:
                return None
            return validate_cover_bytes(
                package.read_member(cover_member, max_bytes=MAX_COVER_IMAGE_BYTES)
            )
    except Exception:
        return None


def validate_cover_bytes(data: bytes) -> ExtractedCover | None:
    if len(data) > MAX_COVER_IMAGE_BYTES:
        return None
    extension = _validated_image_extension(data)
    if extension is None:
        return None
    return ExtractedCover(data=data, extension=extension)


def _find_cover_member(*, opf_root, package: EpubPackage) -> str | None:
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
    return package.resolve_package_reference(href)


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


def _validated_image_extension(data: bytes) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            if image.width * image.height > MAX_COVER_IMAGE_PIXELS:
                return None
            image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ):
        return None
    return cover_extension_for_image_format(image.format or "")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
