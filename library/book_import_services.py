from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional, cast

from django.core.files import File

from .group_services import ensure_book_public_assignment
from .models import Author, Book, BookFile, BookIdentifier, Series


def create_book_from_import_metadata(
    *,
    metadata: dict[str, Any],
    fallback_title: str,
    added_by,
) -> Book:
    authors: list[Author] = []
    for author_name in cast(list[Any], metadata.get("authors") or []):
        name = str(author_name or "").strip()
        if not name:
            continue
        author, _ = Author.objects.get_or_create(name=name)
        authors.append(author)

    series_obj: Series | None = None
    series_name = str(metadata.get("series_name") or "").strip()
    if series_name:
        series_obj, _ = Series.objects.get_or_create(name=series_name)

    series_index_value: Decimal | None = cast(Optional[Decimal], metadata.get("series_index"))

    book = Book.objects.create(
        title=str(metadata.get("title") or "").strip() or fallback_title,
        subtitle=str(metadata.get("subtitle") or "").strip(),
        summary=str(metadata.get("summary") or "").strip(),
        publisher=str(metadata.get("publisher") or "").strip(),
        language=str(metadata.get("language") or "").strip(),
        published_date=metadata.get("published_date"),
        isbn=str(metadata.get("isbn") or "").strip(),
        subjects=metadata.get("subjects") or [],
        series=series_obj,
        series_index=series_index_value,
    )

    if authors:
        book.authors.set(authors)

    ensure_book_public_assignment(book=book, added_by=added_by)
    return book


def create_book_identifiers(*, book: Book, identifiers: list[dict[str, Any]]) -> None:
    for ident in identifiers:
        scheme = str(ident.get("scheme") or "").strip()
        value = str(ident.get("value") or "").strip()
        if not scheme or not value:
            continue
        source = str(ident.get("source") or "").strip()
        is_primary = bool(ident.get("is_primary", False))
        BookIdentifier.objects.get_or_create(
            book=book,
            scheme=scheme,
            value=value,
            defaults={"source": source, "is_primary": is_primary},
        )

    primaries = list(
        BookIdentifier.objects.filter(book=book, is_primary=True).order_by("created_at")
    )
    if len(primaries) > 1:
        for extra in primaries[1:]:
            extra.is_primary = False
            extra.save(update_fields=["is_primary", "updated_at"])


def create_book_file_for_import(
    *,
    book: Book,
    source_path: Path,
    checksum: str,
    file_size: int,
) -> BookFile:
    with source_path.open("rb") as f:
        try:
            _existing_file = cast(Any, book).file
        except BookFile.DoesNotExist:
            _existing_file = None
        if _existing_file is not None:
            raise ValueError("Book already has a file; refusing to create a second BookFile.")

        return BookFile.objects.create(
            book=book,
            file=File(f, name=f"{checksum}.epub"),
            format=BookFile.FORMAT_EPUB,
            checksum=checksum,
            file_size=file_size,
            source_filename=source_path.name,
        )


def persist_new_imported_book(
    *,
    metadata: dict[str, Any],
    source_path: Path,
    checksum: str,
    file_size: int,
    added_by,
    cover_hook: Callable[[Book], None] | None = None,
) -> tuple[Book, BookFile]:
    """
    Persist a newly imported book from normalized metadata.

    Import semantics are create-only: this function assumes the caller has already
    handled duplicate detection and is creating a new Book + BookFile.
    """
    book = create_book_from_import_metadata(
        metadata=metadata,
        fallback_title=source_path.stem,
        added_by=added_by,
    )

    identifiers: list[dict[str, Any]] = cast(list[dict[str, Any]], metadata.get("identifiers") or [])
    create_book_identifiers(book=book, identifiers=identifiers)

    if cover_hook is not None:
        cover_hook(book)

    book_file = create_book_file_for_import(
        book=book, source_path=source_path, checksum=checksum, file_size=file_size
    )
    return book, book_file

