from __future__ import annotations

from typing import Any

from library.models import Book

EPUB_CFI_CONFORMS_TO = "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"


def normalize_epub_cfi(value: object) -> str:
    """
    Tolerant EPUB CFI normalization.

    Accepts either:
    - "epubcfi(...)" strings
    - raw CFI-ish paths like "/6/4"

    Returns:
    - "epubcfi(...)" when it can reasonably wrap a raw value
    - "" for missing/invalid inputs
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("epubcfi("):
        return raw
    return f"epubcfi({raw})"


def build_fragment_selector(cfi: object) -> dict[str, Any]:
    value = normalize_epub_cfi(cfi)
    if not value:
        raise ValueError("CFI is required to build a FragmentSelector")
    return {
        "type": "FragmentSelector",
        "conformsTo": EPUB_CFI_CONFORMS_TO,
        "value": value,
    }


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


def build_target(*, book: Book, current_location: dict[str, Any]) -> dict[str, Any]:
    """
    Build a W3C-ish annotation target from current_location JSON.

    The draft profile expects a `FragmentSelector` with an EPUB CFI value. We only
    require `current_location["cfi"]` for now and preserve the full input under
    `locator` for future use.
    """
    cfi = current_location.get("cfi")
    selector = build_fragment_selector(cfi)
    return {
        "source": build_publication_source(book=book),
        "selector": selector,
        "locator": dict(current_location),
    }

