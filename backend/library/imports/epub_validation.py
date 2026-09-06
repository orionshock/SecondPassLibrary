from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import zipfile

from ebooklib import epub

from library.imports.archives import safe_zip_member_name
from library.imports.errors import InvalidEpubImportError


READ_CHUNK_BYTES = 1024 * 1024
# EPUBs are compressed application archives. The 200 MiB compressed limit fits
# below the web upload ceiling and is shared by direct, batch, and local CLI
# candidates. The internal limits bound work before EbookLib parses archive data.
MAX_EPUB_COMPRESSED_BYTES = 200 * 1024 * 1024
MAX_EPUB_MEMBERS = 2000
MAX_EPUB_MEMBER_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_EPUB_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_EPUB_MEMBER_COMPRESSION_RATIO = 100


@dataclass(frozen=True)
class EpubArchiveLimits:
    compressed_bytes: int
    members: int
    member_uncompressed_bytes: int
    total_uncompressed_bytes: int
    member_compression_ratio: int


# Browser uploads are untrusted and are parsed in the web process. These limits
# retain ample room for image-heavy EPUBs while bounding one request to a
# home-server-appropriate working set. Trusted local import commands keep the
# established defaults above.
WEB_EPUB_LIMITS = EpubArchiveLimits(
    compressed_bytes=64 * 1024 * 1024,
    members=1000,
    member_uncompressed_bytes=32 * 1024 * 1024,
    total_uncompressed_bytes=256 * 1024 * 1024,
    member_compression_ratio=50,
)


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


def validate_epub_bytes(
    data: bytes, *, limits: EpubArchiveLimits | None = None
) -> None:
    if limits is None:
        validate_epub_archive(data)
    else:
        validate_epub_archive(
            data,
            max_compressed_bytes=limits.compressed_bytes,
            max_members=limits.members,
            max_member_uncompressed_bytes=limits.member_uncompressed_bytes,
            max_total_uncompressed_bytes=limits.total_uncompressed_bytes,
            max_member_compression_ratio=limits.member_compression_ratio,
        )
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
