from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.db import transaction

from library.groups.public_group import get_public_group
from library.groups.services import add_book_to_group
from library.imports.dto import ImportMetadata
from library.catalog.tag_services import resolve_catalog_tag
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    Series,
)


IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_DUPLICATE = "duplicate"
IMPORT_STATUS_CONFLICT = "conflict"


@dataclass(frozen=True)
class ImportPersistenceResult:
    status: str
    book: Book
    message: str = ""


def persist_imported_book(
    *,
    metadata: ImportMetadata,
    checksum: str | None,
    file_size: int | None = None,
    book_file: File | None = None,
    actor=None,
) -> ImportPersistenceResult:
    _validate_import_inputs(metadata=metadata, checksum=checksum, book_file=book_file)
    existing = Book.objects.filter(checksum=checksum).first()
    if existing is not None:
        return ImportPersistenceResult(
            status=IMPORT_STATUS_DUPLICATE,
            book=existing,
            message="A book with this checksum already exists.",
        )
    identifier_conflict = _find_identifier_conflict(metadata)
    if identifier_conflict is not None:
        return ImportPersistenceResult(
            status=IMPORT_STATUS_CONFLICT,
            book=identifier_conflict.book,
            message="An identifier from this import already belongs to another book.",
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
        )
        if book_file is not None:
            _attach_book_file(book=book, book_file=book_file)
        _persist_authors(book=book, metadata=metadata)
        _persist_series(book=book, metadata=metadata)
        _persist_tags(book=book, metadata=metadata)
        _persist_identifiers(book=book, metadata=metadata)
        add_book_to_group(book=book, group=get_public_group(), actor=actor)

    return ImportPersistenceResult(status=IMPORT_STATUS_IMPORTED, book=book)


def _attach_book_file(*, book: Book, book_file) -> None:
    filename = f"{book.checksum}.{book.file_format}"
    book.book_file.save(filename, book_file, save=True)


def _validate_import_inputs(
    *, metadata: ImportMetadata, checksum: str | None, book_file: File | None
) -> None:
    if not str(checksum or "").strip():
        raise ValidationError("Checksum is required.")
    if not metadata.title.strip():
        raise ValidationError("Title is required.")
    if book_file is not None and not isinstance(book_file, File):
        raise ValidationError("book_file must be a Django File.")


def _find_identifier_conflict(metadata: ImportMetadata) -> BookIdentifier | None:
    for identifier in metadata.identifiers:
        existing = (
            BookIdentifier.objects.filter(
                scheme=identifier.scheme,
                normalized_value=identifier.normalized_value,
            )
            .select_related("book")
            .first()
        )
        if existing is not None:
            return existing
    return None


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
        _fill_blank_sort_name(existing, sort_name=sort_name)
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
        _fill_blank_sort_name(existing, sort_name=sort_name)
        return existing
    return Series.objects.create(name=name, sort_name=sort_name)


def _fill_blank_sort_name(instance, *, sort_name: str) -> None:
    if instance.sort_name or not sort_name:
        return
    instance.sort_name = sort_name
    instance.save(update_fields=["sort_name", "updated_at"])


def _persist_tags(*, book: Book, metadata: ImportMetadata) -> None:
    for tag_metadata in metadata.tags:
        tag = resolve_catalog_tag(tag_metadata.name)
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
