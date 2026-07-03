"""W3C-influenced helpers that are still used by the live annotation API."""

from __future__ import annotations

from typing import Any

from library.models import Book


def build_publication_source(*, book: Book) -> dict[str, Any]:
    """
    Build a stable-ish target source object for an annotation.

    - Prefer content-addressed identity when a BookFile checksum exists.
    - Fall back to the book UUID.
    """
    book_file = getattr(book, "file", None)
    checksum = getattr(book_file, "checksum", None) if book_file is not None else None

    if isinstance(checksum, str) and checksum.strip():
        source_id = f"book:sha256:{checksum}"
        file_hash = f"sha256:{checksum}"
    else:
        source_id = f"urn:uuid:{book.id}"
        file_hash = None

    author_names: list[str] = []
    authors = getattr(book, "authors", None)
    if authors is not None:
        author_names = [a.name for a in authors.all()]

    source: dict[str, Any] = {
        "id": source_id,
        "type": "Book",
        "title": book.title,
    }
    if author_names:
        source["author"] = author_names
    if file_hash is not None:
        source["fileHash"] = file_hash
    return source
