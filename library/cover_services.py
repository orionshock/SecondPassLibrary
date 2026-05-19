from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from django.core.files.base import ContentFile

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

