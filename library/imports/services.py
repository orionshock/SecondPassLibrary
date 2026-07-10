from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from library.groups.public_group import get_public_group
from library.groups.services import add_book_to_group
from library.imports.dto import ImportMetadata
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    Series,
)


IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_DUPLICATE = "duplicate"


@dataclass(frozen=True)
class ImportPersistenceResult:
    status: str
    book: Book
    message: str = ""


def persist_imported_book(
    *,
    metadata: ImportMetadata,
    checksum: str,
    file_size: int | None = None,
    source_filename: str = "",
    book_file: Any = None,
    actor=None,
) -> ImportPersistenceResult:
    existing = Book.objects.filter(checksum=checksum).first()
    if existing is not None:
        return ImportPersistenceResult(
            status=IMPORT_STATUS_DUPLICATE,
            book=existing,
            message="A book with this checksum already exists.",
        )

    with transaction.atomic():
        book = Book.objects.create(
            title=metadata.title,
            sort_title=metadata.sort_title,
            subtitle=metadata.subtitle,
            language=metadata.language,
            publisher=metadata.publisher,
            description=metadata.description,
            published_year=metadata.published_year,
            published_month=metadata.published_month,
            published_day=metadata.published_day,
            published_date_precision=metadata.published_date_precision,
            file_format=Book.FILE_FORMAT_EPUB,
            checksum=checksum,
            file_size=file_size,
            source_filename=source_filename,
        )
        if book_file is not None:
            _attach_book_file(book=book, book_file=book_file, source_filename=source_filename)
        _persist_authors(book=book, metadata=metadata)
        _persist_series(book=book, metadata=metadata)
        _persist_tags(book=book, metadata=metadata)
        _persist_identifiers(book=book, metadata=metadata)
        add_book_to_group(book=book, group=get_public_group(), actor=actor)

    return ImportPersistenceResult(status=IMPORT_STATUS_IMPORTED, book=book)


def _attach_book_file(*, book: Book, book_file, source_filename: str) -> None:
    filename = source_filename or f"{book.checksum}.{book.file_format}"
    if hasattr(book_file, "read"):
        book.book_file.save(filename, book_file, save=True)
        return
    book.book_file = book_file
    book.save(update_fields=["book_file", "updated_at"])


def _persist_authors(*, book: Book, metadata: ImportMetadata) -> None:
    for author_metadata in metadata.authors:
        author = _get_or_create_author(
            name=author_metadata.name,
            sort_name=author_metadata.sort_name,
        )
        BookAuthor.objects.create(
            book=book,
            author=author,
            position=author_metadata.position,
        )


def _get_or_create_author(*, name: str, sort_name: str) -> Author:
    existing = Author.objects.filter(name__iexact=name).order_by("id").first()
    if existing is not None:
        return existing
    return Author.objects.create(name=name, sort_name=sort_name)


def _persist_series(*, book: Book, metadata: ImportMetadata) -> None:
    if metadata.series is None:
        return
    series = _get_or_create_series(
        name=metadata.series.name,
        sort_name=metadata.series.sort_name,
    )
    BookSeries.objects.create(
        book=book,
        series=series,
        series_index=metadata.series.series_index,
    )


def _get_or_create_series(*, name: str, sort_name: str) -> Series:
    existing = Series.objects.filter(name__iexact=name).order_by("id").first()
    if existing is not None:
        return existing
    return Series.objects.create(name=name, sort_name=sort_name)


def _persist_tags(*, book: Book, metadata: ImportMetadata) -> None:
    for tag_metadata in metadata.tags:
        tag, _created = CatalogTag.objects.get_or_create(
            normalized_name=tag_metadata.normalized_name,
            defaults={"name": tag_metadata.name, "sort_name": tag_metadata.sort_name},
        )
        BookCatalogTag.objects.create(book=book, catalog_tag=tag)


def _persist_identifiers(*, book: Book, metadata: ImportMetadata) -> None:
    for identifier in metadata.identifiers:
        if BookIdentifier.objects.filter(
            scheme=identifier.scheme,
            normalized_value=identifier.normalized_value,
        ).exists():
            continue
        BookIdentifier.objects.create(
            book=book,
            scheme=identifier.scheme,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
        )
