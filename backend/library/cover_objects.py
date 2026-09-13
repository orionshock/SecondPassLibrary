from __future__ import annotations

from pathlib import Path
import re


COVER_STORAGE_PREFIX = "covers/"
PUBLIC_COVER_PATH_PREFIX = "/media/covers/"
IMMUTABLE_COVER_CACHE_CONTROL = "public, max-age=31536000, immutable"

_COVER_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
SUPPORTED_COVER_EXTENSIONS = frozenset(
    extension for extension, _media_type in _COVER_FORMATS.values()
)
SUPPORTED_COVER_MEDIA_TYPES = frozenset(
    media_type for _extension, media_type in _COVER_FORMATS.values()
)

_COVER_EXTENSION_PATTERN = "|".join(
    re.escape(extension.removeprefix("."))
    for extension in sorted(SUPPORTED_COVER_EXTENSIONS)
)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_RELATIVE_PATH_RE = re.compile(
    r"^(?P<first>[0-9a-f]{2})/(?P<second>[0-9a-f]{2})/"
    rf"(?P<digest>[0-9a-f]{{64}})(?P<extension>\.(?:{_COVER_EXTENSION_PATTERN}))$"
)
_COVER_FILENAME_RE = re.compile(
    rf"^(?P<digest>[0-9a-f]{{64}})(?P<extension>\.(?:{_COVER_EXTENSION_PATTERN}))$"
)


def cover_extension_for_image_format(image_format: str) -> str | None:
    cover_format = _COVER_FORMATS.get((image_format or "").upper())
    return cover_format[0] if cover_format is not None else None


def canonical_cover_storage_name(*, digest: str, extension: str) -> str:
    normalized_extension = (extension or "").lower()
    if not _DIGEST_RE.fullmatch(digest) or normalized_extension not in SUPPORTED_COVER_EXTENSIONS:
        raise ValueError("Cover identity requires a SHA-256 digest and supported extension.")
    return (
        f"{COVER_STORAGE_PREFIX}{digest[:2]}/{digest[2:4]}/"
        f"{digest}{normalized_extension}"
    )


def canonical_cover_storage_name_from_filename(filename: str) -> str:
    match = _COVER_FILENAME_RE.fullmatch(Path(filename).name)
    if match is None:
        raise ValueError("Cover filename must be '<sha256>.<ext>'.")
    return canonical_cover_storage_name(
        digest=match.group("digest"),
        extension=match.group("extension"),
    )


def is_canonical_cover_storage_name(name: str) -> bool:
    if not name.startswith(COVER_STORAGE_PREFIX):
        return False
    return is_canonical_cover_relative_path(name.removeprefix(COVER_STORAGE_PREFIX))


def is_canonical_cover_relative_path(path: str) -> bool:
    match = _CANONICAL_RELATIVE_PATH_RE.fullmatch(path)
    if match is None:
        return False
    digest = match.group("digest")
    return match.group("first") == digest[:2] and match.group("second") == digest[2:4]


def is_immutable_public_cover_path(path: str) -> bool:
    if not path.startswith(PUBLIC_COVER_PATH_PREFIX):
        return False
    return is_canonical_cover_relative_path(
        path.removeprefix(PUBLIC_COVER_PATH_PREFIX)
    )
