from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .epub_services import calculate_file_sha256


@dataclass(frozen=True)
class BookFileUploadMetadata:
    checksum: str
    file_size: int
    source_filename: str


def inspect_epub_upload(upload) -> BookFileUploadMetadata:
    source_filename = Path(str(getattr(upload, "name", ""))).name
    if Path(source_filename).suffix.lower() != ".epub":
        raise ValueError("Book file must be an EPUB file.")

    checksum, file_size = calculate_file_sha256(upload)
    return BookFileUploadMetadata(
        checksum=checksum,
        file_size=file_size,
        source_filename=source_filename,
    )
