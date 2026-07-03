from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse
import zipfile
import posixpath
import warnings

from django.core.files.base import ContentFile
from defusedxml import ElementTree as SafeElementTree

from PIL import Image
from PIL import ImageFile
from PIL import UnidentifiedImageError

from .models import Book


CoverSource = Literal["epub", "opf_sidecar", "manual", "unknown"]


@dataclass(frozen=True)
class CoverImageInfo:
    sha256: str
    mime: str
    extension: str
    width: int
    height: int
    pil_format: str


MAX_COVER_BYTES = 5 * 1024 * 1024
MAX_COVER_DIMENSION = 8000
MAX_OPF_XML_BYTES = 512 * 1024
MAX_CONTAINER_XML_BYTES = 128 * 1024


_FORMAT_TO_MIME_EXT: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


def validate_cover_image_bytes(
    *, data: bytes, source_filename: str | None = None
) -> CoverImageInfo:
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("Cover data must be bytes.")

    if len(data) == 0:
        raise ValueError("Cover image is empty.")

    if len(data) > MAX_COVER_BYTES:
        raise ValueError("Cover image exceeds 5MB limit.")

    # Pillow defaults are generally safe, but explicitly disable truncated images.
    previous_load_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        bomb_warning = getattr(Image, "DecompressionBombWarning", None)
        bomb_error = getattr(Image, "DecompressionBombError", None)

        try:
            with warnings.catch_warnings():
                if bomb_warning is not None:
                    warnings.simplefilter("error", bomb_warning)

                with Image.open(BytesIO(data)) as img:
                    # Ensure the image decodes (not just header-parse).
                    img.load()

                    pil_format = (img.format or "").upper().strip()
                    if pil_format not in _FORMAT_TO_MIME_EXT:
                        raise ValueError("Unsupported cover image format (JPEG/PNG/WEBP only).")

                    width, height = img.size
                    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
                        raise ValueError("Invalid cover image dimensions.")

                    if width > MAX_COVER_DIMENSION or height > MAX_COVER_DIMENSION:
                        raise ValueError("Cover image dimensions are too large.")

                    mime, ext = _FORMAT_TO_MIME_EXT[pil_format]
        except UnidentifiedImageError as exc:
            filename_note = f" ({source_filename})" if source_filename else ""
            raise ValueError(f"Invalid or corrupt cover image{filename_note}.") from exc
        except Exception as exc:
            if bomb_error is not None and isinstance(exc, bomb_error):
                raise ValueError("Cover image rejected (possible decompression bomb).") from exc
            if bomb_warning is not None and isinstance(exc, bomb_warning):
                raise ValueError("Cover image rejected (possible decompression bomb).") from exc
            raise
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = previous_load_truncated

    sha = hashlib.sha256(data).hexdigest()
    return CoverImageInfo(
        sha256=sha,
        mime=mime,
        extension=ext,
        width=width,
        height=height,
        pil_format=pil_format,
    )


def set_book_cover_from_bytes(
    *,
    book: Book,
    data: bytes,
    source: CoverSource,
    source_filename: str | None = None,
    save: bool = True,
) -> CoverImageInfo:
    info = validate_cover_image_bytes(data=data, source_filename=source_filename)

    # Content-addressed filename; upload_to derives the final path.
    name = f"{info.sha256}{info.extension}"
    book.cover_file.save(name, ContentFile(data), save=False)

    book.cover_source = source
    book.cover_mime = info.mime
    book.cover_width = info.width
    book.cover_height = info.height

    if save:
        book.save(
            update_fields=[
                "cover_file",
                "cover_source",
                "cover_mime",
                "cover_width",
                "cover_height",
                "updated_at",
            ]
        )

    return info


def _is_url_like_href(href: str) -> bool:
    h = (href or "").strip()
    if not h:
        return True
    parsed = urlparse(h)
    return parsed.scheme.lower() in {"http", "https", "data"}


def _safe_posix_relpath(path: str) -> str | None:
    p = (path or "").strip()
    if not p:
        return None

    # Reject URL-like and drive-letter-ish paths early.
    if _is_url_like_href(p):
        return None
    if p.startswith(("/", "\\")):
        return None
    if ":" in p:
        return None

    # EPUB uses forward slashes; normalize defensively.
    p = p.replace("\\", "/")
    pure = PurePosixPath(p)
    if pure.is_absolute():
        return None
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None

    normalized = posixpath.normpath(p)
    if normalized.startswith("../") or normalized == "..":
        return None
    if normalized.startswith("/"):
        return None
    return normalized


def _read_zip_member_bytes(
    *, zf: zipfile.ZipFile, member: str, max_bytes: int
) -> bytes | None:
    try:
        info = zf.getinfo(member)
    except KeyError:
        return None

    if info.file_size is not None and info.file_size > max_bytes:
        return None

    with zf.open(info, "r") as fp:
        data = fp.read(max_bytes + 1)
    if len(data) > max_bytes:
        return None
    return data


def _parse_xml_bytes(*, data: bytes) -> SafeElementTree.Element:
    return SafeElementTree.fromstring(data)


def _find_opf_path_from_container_xml(container_xml: bytes) -> str | None:
    try:
        root = _parse_xml_bytes(data=container_xml)
    except Exception:
        return None

    # container.xml typically uses the namespace:
    # urn:oasis:names:tc:opendocument:xmlns:container
    rootfiles = list(root.iter())
    for el in rootfiles:
        if el.tag.endswith("rootfile"):
            full_path = (el.attrib.get("full-path") or "").strip()
            return _safe_posix_relpath(full_path)
    return None


def _find_cover_href_from_opf(opf_xml: bytes) -> str | None:
    try:
        root = _parse_xml_bytes(data=opf_xml)
    except Exception:
        return None

    # 1) EPUB3: manifest item properties includes cover-image
    for el in root.iter():
        if not el.tag.endswith("item"):
            continue
        props = (el.attrib.get("properties") or "").lower()
        if "cover-image" not in props:
            continue
        href = (el.attrib.get("href") or "").strip()
        safe = _safe_posix_relpath(href)
        if safe is not None:
            return safe

    # 2) EPUB2: <meta name="cover" content="manifest-id">
    cover_id: str | None = None
    for el in root.iter():
        if not el.tag.endswith("meta"):
            continue
        name = (el.attrib.get("name") or "").strip().lower()
        if name != "cover":
            continue
        cover_id = (el.attrib.get("content") or "").strip()
        if cover_id:
            break

    if not cover_id:
        return None

    for el in root.iter():
        if not el.tag.endswith("item"):
            continue
        if (el.attrib.get("id") or "").strip() != cover_id:
            continue
        href = (el.attrib.get("href") or "").strip()
        safe = _safe_posix_relpath(href)
        if safe is not None:
            return safe

    return None


def find_cover_href_in_opf(*, opf_xml: bytes) -> str | None:
    """
    Return a safe OPF-relative cover href if discoverable, else None.

    This does not join against any base directory; callers must resolve relative to
    the OPF's directory (e.g. within an EPUB zip, or within a ZIP import folder).
    """
    return _find_cover_href_from_opf(opf_xml)


def extract_epub_embedded_cover_to_book(
    *, book: Book, epub_path: str, save: bool = True
) -> bool:
    """
    Attempt to extract an embedded cover image from an EPUB file and store it on the Book.

    Returns True if a cover was found and stored, False otherwise.

    Notes:
    - This is best-effort and should not fail the import if cover parsing/validation fails.
    - This does not overwrite an existing cover.
    """
    if getattr(book, "cover_file", None):
        return False

    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container_member = "META-INF/container.xml"
            container_xml = _read_zip_member_bytes(
                zf=zf, member=container_member, max_bytes=MAX_CONTAINER_XML_BYTES
            )
            if not container_xml:
                return False

            opf_path = _find_opf_path_from_container_xml(container_xml)
            if not opf_path:
                return False

            opf_xml = _read_zip_member_bytes(
                zf=zf, member=opf_path, max_bytes=MAX_OPF_XML_BYTES
            )
            if not opf_xml:
                return False

            cover_href = _find_cover_href_from_opf(opf_xml)
            if not cover_href:
                return False

            opf_dir = posixpath.dirname(opf_path)
            cover_member = (
                posixpath.normpath(posixpath.join(opf_dir, cover_href))
                if opf_dir
                else cover_href
            )
            cover_member = _safe_posix_relpath(cover_member) or ""
            if not cover_member:
                return False

            cover_bytes = _read_zip_member_bytes(
                zf=zf, member=cover_member, max_bytes=MAX_COVER_BYTES
            )
            if not cover_bytes:
                return False

            # Validate + store original bytes.
            set_book_cover_from_bytes(
                book=book,
                data=cover_bytes,
                source="epub",
                source_filename=posixpath.basename(cover_member) or None,
                save=save,
            )
            return True
    except Exception:
        return False
