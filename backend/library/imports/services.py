from __future__ import annotations

from dataclasses import dataclass
import logging

from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.files.storage import Storage
from django.db import transaction

from core.rich_text import sanitize_descriptive_prose
from library.catalog.names import (
    AmbiguousCatalogEntityName,
    find_single_normalized_name_match,
    normalize_catalog_entity_name,
)
from library.catalog.tag_services import resolve_catalog_tag
from library.groups.book_assignments import add_book_to_group
from library.groups.public_group import get_public_group
from library.imports.dto import ImportMetadata
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    Series,
)
from library.series_indexes import normalize_series_index
from library.storage_diagnostics import log_storage_issue


IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_DUPLICATE = "duplicate"
IMPORT_STATUS_CONFLICT = "conflict"
logger = logging.getLogger(__name__)
ROLLBACK_CLEANUP_DISPOSITION_ATTRIBUTE = "_import_rollback_cleanup_disposition"


@dataclass(frozen=True)
class ImportPersistenceResult:
    status: str
    book: Book | None
    message: str = ""
    error_category: str = ""
    ambiguity: AmbiguousCatalogEntityName | None = None


@dataclass(frozen=True)
class _StoredBookFile:
    storage: Storage
    name: str
    created: bool


def persist_imported_book(
    *,
    metadata: ImportMetadata,
    checksum: str | None,
    file_size: int | None = None,
    book_file: File | None = None,
    actor=None,
) -> ImportPersistenceResult:
    _validate_import_inputs(metadata=metadata, checksum=checksum, book_file=book_file)
    # Exact bytes are the duplicate-file identity; bibliographic identifiers are
    # non-unique metadata and never collapse two Books.
    existing = Book.objects.filter(checksum=checksum).first()
    if existing is not None:
        return ImportPersistenceResult(
            status=IMPORT_STATUS_DUPLICATE,
            book=existing,
            message=(
                "This exact EPUB file is already in the library. "
                "No action is needed unless you intended to import a different file."
            ),
        )

    try:
        existing_authors = [
            find_single_normalized_name_match(
                model=Author,
                name=author.name,
                kind="Author",
            )
            for author in metadata.authors
        ]
        existing_series = (
            find_single_normalized_name_match(
                model=Series,
                name=metadata.series.name,
                kind="Series",
            )
            if metadata.series is not None
            else None
        )
    except AmbiguousCatalogEntityName as exc:
        return ImportPersistenceResult(
            status=IMPORT_STATUS_CONFLICT,
            book=None,
            message=_ambiguous_entity_message(exc),
            error_category=f"{exc.kind.casefold()}_ambiguous",
            ambiguity=exc,
        )

    stored_file: _StoredBookFile | None = None
    book: Book | None = None
    try:
        with transaction.atomic():
            book = Book.objects.create(
                title=metadata.title,
                sort_title=metadata.sort_title,
                subtitle=metadata.subtitle,
                language=metadata.language,
                publisher=metadata.publisher,
                description=sanitize_descriptive_prose(
                    metadata.description, field_name="description"
                ),
                published_year=metadata.published_year,
                published_month=metadata.published_month,
                published_day=metadata.published_day,
                published_date_precision=metadata.published_date_precision,
                file_format=Book.FILE_FORMAT_EPUB,
                checksum=checksum,
                file_size=file_size,
            )
            if book_file is not None:
                stored_file = _acquire_book_file(book=book, book_file=book_file)
                _attach_book_file(book=book, stored_file=stored_file)
            _persist_authors(
                book=book,
                metadata=metadata,
                existing_authors=existing_authors,
            )
            _persist_series(
                book=book,
                metadata=metadata,
                existing_series=existing_series,
            )
            _persist_tags(book=book, metadata=metadata)
            _persist_identifiers(book=book, metadata=metadata)
            add_book_to_group(book=book, group=get_public_group(), actor=actor)
    except Exception as exc:
        cleanup_status = "not_needed"
        if stored_file is not None and not stored_file.created:
            cleanup_status = "preserved_reused"
        elif stored_file is not None:
            # Cleanup is best effort so its failure cannot replace the persistence
            # error from the rolled-back import.
            cleanup_status = _cleanup_rolled_back_book_file(
                stored_file=stored_file, book=book, actor=actor
            )
        # Diagnostics must not become a new failure path. Some third-party
        # exception types may reject arbitrary attributes.
        try:
            setattr(exc, ROLLBACK_CLEANUP_DISPOSITION_ATTRIBUTE, cleanup_status)
        except Exception:
            pass
        raise

    return ImportPersistenceResult(status=IMPORT_STATUS_IMPORTED, book=book)


def _ambiguous_entity_message(exc: AmbiguousCatalogEntityName) -> str:
    plural = "Authors" if exc.kind == "Author" else "Series"
    return (
        f'Multiple existing {plural} match "{exc.display_name}" '
        f"({exc.match_count} matches). The importer cannot safely determine "
        f"which {exc.kind} belongs to this Book. Resolve the ambiguous {exc.kind} "
        "records or adjust the source metadata, then retry the import."
    )


def _acquire_book_file(*, book: Book, book_file) -> _StoredBookFile:
    filename = f"{book.checksum}.{book.file_format}"
    field = Book._meta.get_field("book_file")
    storage = field.storage
    target_name = field.generate_filename(book, filename)
    created = not storage.exists(target_name)
    stored_name = storage.save(target_name, book_file) if created else target_name
    stored_name = stored_name.replace("\\", "/")
    return _StoredBookFile(storage=storage, name=stored_name, created=created)


def _attach_book_file(*, book: Book, stored_file: _StoredBookFile) -> None:
    book.book_file.name = stored_file.name
    book.save(update_fields=["book_file", "updated_at"])


def _cleanup_rolled_back_book_file(
    *, stored_file: _StoredBookFile, book: Book | None, actor=None
) -> str:
    try:
        if Book.objects.filter(book_file=stored_file.name).exists():
            return "preserved_reference"
        if stored_file.storage.exists(stored_file.name):
            stored_file.storage.delete(stored_file.name)
        return "complete"
    except Exception as exc:
        try:
            log_storage_issue(
                logger,
                action="new_epub_rollback_cleanup",
                book_id=getattr(book, "pk", None),
                actor=actor,
                reason="delete-failed",
                exc=exc,
                storage_name=stored_file.name,
            )
        except Exception:
            # Rollback diagnostics are subordinate to the original persistence
            # failure and must never replace it.
            pass
        return "failed"


def _validate_import_inputs(
    *, metadata: ImportMetadata, checksum: str | None, book_file: File | None
) -> None:
    if not str(checksum or "").strip():
        raise ValidationError("Checksum is required.")
    if not metadata.title.strip():
        raise ValidationError("Title is required.")
    if book_file is not None and not isinstance(book_file, File):
        raise ValidationError("book_file must be a Django File.")


def _persist_authors(
    *,
    book: Book,
    metadata: ImportMetadata,
    existing_authors: list[Author | None],
) -> None:
    for author_metadata, existing in zip(
        metadata.authors, existing_authors, strict=True
    ):
        author = _get_or_create_author(
            name=author_metadata.name,
            sort_name=author_metadata.sort_name,
            existing=existing,
        )
        BookAuthor.objects.create(
            book=book,
            author=author,
            position=author_metadata.position,
        )


def _get_or_create_author(
    *, name: str, sort_name: str, existing: Author | None
) -> Author:
    if existing is not None:
        _fill_blank_sort_name(existing, sort_name=sort_name)
        return existing
    return Author.objects.create(
        name=name,
        sort_name=sort_name,
        normalized_name=normalize_catalog_entity_name(name),
    )


def _persist_series(
    *,
    book: Book,
    metadata: ImportMetadata,
    existing_series: Series | None,
) -> None:
    if metadata.series is None:
        return
    series = _get_or_create_series(
        name=metadata.series.name,
        sort_name=metadata.series.sort_name,
        existing=existing_series,
    )
    BookSeries.objects.create(
        book=book,
        series=series,
        series_index=normalize_series_index(metadata.series.series_index),
    )


def _get_or_create_series(
    *, name: str, sort_name: str, existing: Series | None
) -> Series:
    if existing is not None:
        _fill_blank_sort_name(existing, sort_name=sort_name)
        return existing
    return Series.objects.create(
        name=name,
        sort_name=sort_name,
        normalized_name=normalize_catalog_entity_name(name),
    )


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
    persisted_keys: set[tuple[str, str]] = set()
    for identifier in metadata.identifiers:
        key = (identifier.scheme, identifier.normalized_value)
        if key in persisted_keys:
            continue
        BookIdentifier.objects.create(
            book=book,
            scheme=identifier.scheme,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
        )
        persisted_keys.add(key)
