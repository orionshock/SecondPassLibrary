from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase

from library.groups.public_group import get_public_group
from library.imports.dto import (
    ImportAuthor,
    ImportIdentifier,
    ImportMetadata,
    ImportSeries,
    ImportTag,
)
from library.imports.services import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_IMPORTED,
    persist_imported_book,
)
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookGroupAssignment,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    Series,
)


class ImportPersistenceServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user(username="importer", password="pw")

    def test_persists_basic_book_fields_from_dto(self):
        result = persist_imported_book(
            metadata=sample_metadata(),
            checksum="abc123",
            file_size=1234,
            source_filename="sample.epub",
            actor=self.actor,
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        book = result.book
        self.assertEqual(book.title, "Sample Book")
        self.assertEqual(book.sort_title, "Sample Book, The")
        self.assertEqual(book.subtitle, "A Subtitle")
        self.assertEqual(book.language, "en")
        self.assertEqual(book.publisher, "Example Press")
        self.assertEqual(book.description, "Example description")
        self.assertEqual(book.file_format, Book.FILE_FORMAT_EPUB)
        self.assertEqual(book.checksum, "abc123")
        self.assertEqual(book.file_size, 1234)
        self.assertEqual(book.source_filename, "sample.epub")

    def test_persists_partial_published_date_fields(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                published_year=2024,
                published_month=7,
                published_day=None,
                published_date_precision=Book.DATE_PRECISION_MONTH,
            ),
            checksum="date123",
        )

        book = result.book
        self.assertEqual(book.published_year, 2024)
        self.assertEqual(book.published_month, 7)
        self.assertIsNone(book.published_day)
        self.assertEqual(book.published_date_precision, Book.DATE_PRECISION_MONTH)

    def test_creates_authors_and_book_author_positions(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(name="First Author", sort_name="Author, First", position=0),
                    ImportAuthor(name="Second Author", sort_name="Author, Second", position=1),
                ]
            ),
            checksum="authors123",
        )

        rows = list(BookAuthor.objects.filter(book=result.book).order_by("position"))
        self.assertEqual([row.author.name for row in rows], ["First Author", "Second Author"])
        self.assertEqual([row.position for row in rows], [0, 1])

    def test_reuses_existing_author_by_display_identity(self):
        existing = Author.objects.create(name="Existing Author", sort_name="Author, Existing")

        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[ImportAuthor(name="existing author", sort_name="Different", position=0)]
            ),
            checksum="reuse-author",
        )

        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(BookAuthor.objects.get(book=result.book).author, existing)

    def test_existing_author_blank_sort_name_is_filled(self):
        existing = Author.objects.create(name="Existing Author", sort_name="")

        persist_imported_book(
            metadata=sample_metadata(
                authors=[ImportAuthor(name="existing author", sort_name="Author, Existing", position=0)]
            ),
            checksum="fill-author-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Author, Existing")

    def test_existing_author_nonblank_sort_name_is_preserved(self):
        existing = Author.objects.create(name="Existing Author", sort_name="Original Sort")

        persist_imported_book(
            metadata=sample_metadata(
                authors=[ImportAuthor(name="existing author", sort_name="Different Sort", position=0)]
            ),
            checksum="preserve-author-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Original Sort")

    def test_creates_series_and_book_series_index(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(
                    name="Series Name",
                    sort_name="Series Name",
                    series_index=Decimal("2.50"),
                )
            ),
            checksum="series123",
        )

        row = BookSeries.objects.get(book=result.book)
        self.assertEqual(row.series.name, "Series Name")
        self.assertEqual(row.series_index, Decimal("2.50"))

    def test_existing_series_blank_sort_name_is_filled(self):
        existing = Series.objects.create(name="Series Name", sort_name="")

        persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(name="series name", sort_name="Series Sort", series_index=None)
            ),
            checksum="fill-series-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Series Sort")

    def test_existing_series_nonblank_sort_name_is_preserved(self):
        existing = Series.objects.create(name="Series Name", sort_name="Original Series Sort")

        persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(name="series name", sort_name="Different Sort", series_index=None)
            ),
            checksum="preserve-series-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Original Series Sort")

    def test_creates_and_reuses_catalog_tags_by_normalized_name(self):
        existing = CatalogTag.objects.create(
            name="Science Fiction",
            sort_name="Science Fiction",
            normalized_name="science fiction",
        )

        result = persist_imported_book(
            metadata=sample_metadata(
                tags=[
                    ImportTag(
                        name="sci fi display ignored",
                        sort_name="sci fi display ignored",
                        normalized_name="science fiction",
                    ),
                    ImportTag(name="Space Opera", sort_name="Space Opera", normalized_name="space opera"),
                ]
            ),
            checksum="tags123",
        )

        tags = list(
            BookCatalogTag.objects.filter(book=result.book)
            .select_related("catalog_tag")
            .order_by("catalog_tag__normalized_name")
        )
        self.assertEqual([row.catalog_tag for row in tags], [existing, CatalogTag.objects.get(normalized_name="space opera")])

    def test_creates_identifiers_with_normalized_uniqueness(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                identifiers=[
                    ImportIdentifier(
                        scheme=BookIdentifier.SCHEME_ISBN_13,
                        value="978-0-00-000001-1",
                        normalized_value="9780000000011",
                    ),
                    ImportIdentifier(
                        scheme=BookIdentifier.SCHEME_DOI,
                        value="10.1000/abc",
                        normalized_value="10.1000/abc",
                    ),
                ]
            ),
            checksum="identifiers123",
        )

        self.assertEqual(
            list(
                BookIdentifier.objects.filter(book=result.book)
                .order_by("scheme")
                .values_list("scheme", "normalized_value")
            ),
            [(BookIdentifier.SCHEME_DOI, "10.1000/abc"), (BookIdentifier.SCHEME_ISBN_13, "9780000000011")],
        )

    def test_duplicate_checksum_returns_duplicate_without_second_book(self):
        existing = Book.objects.create(title="Existing", checksum="duplicate123")

        result = persist_imported_book(metadata=sample_metadata(), checksum="duplicate123")

        self.assertEqual(result.status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(result.book, existing)
        self.assertEqual(Book.objects.filter(checksum="duplicate123").count(), 1)

    def test_blank_checksum_is_rejected(self):
        with self.assertRaises(ValidationError):
            persist_imported_book(metadata=sample_metadata(), checksum="")

    def test_missing_checksum_is_rejected(self):
        with self.assertRaises(ValidationError):
            persist_imported_book(metadata=sample_metadata(), checksum=None)

    def test_blank_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            persist_imported_book(metadata=sample_metadata(title=""), checksum="blank-title")

    def test_duplicate_identifier_on_another_book_returns_conflict(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing-identifier")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )

        result = persist_imported_book(
            metadata=sample_metadata(
                identifiers=[
                    ImportIdentifier(
                        scheme=BookIdentifier.SCHEME_ISBN_13,
                        value="978-0-00-000001-1",
                        normalized_value="9780000000011",
                    )
                ]
            ),
            checksum="identifier-conflict",
        )

        self.assertEqual(result.status, IMPORT_STATUS_CONFLICT)
        self.assertEqual(result.book, existing_book)
        self.assertFalse(Book.objects.filter(checksum="identifier-conflict").exists())

    def test_new_book_is_assigned_to_public_common_room(self):
        result = persist_imported_book(metadata=sample_metadata(), checksum="public123")

        self.assertTrue(
            BookGroupAssignment.objects.filter(book=result.book, group=get_public_group()).exists()
        )

    def test_public_assignment_added_by_is_actor(self):
        result = persist_imported_book(
            metadata=sample_metadata(),
            checksum="actor123",
            actor=self.actor,
        )

        assignment = BookGroupAssignment.objects.get(book=result.book, group=get_public_group())
        self.assertEqual(assignment.added_by, self.actor)

    def test_no_bookfile_model_or_object_appears(self):
        result = persist_imported_book(metadata=sample_metadata(), checksum="no-bookfile")

        self.assertFalse(hasattr(__import__("library.models").models, "BookFile"))
        self.assertEqual(result.book.book_file.name, "")

    def test_omitted_book_file_leaves_book_file_blank(self):
        result = persist_imported_book(metadata=sample_metadata(), checksum="omit-book-file")

        self.assertEqual(result.book.book_file.name, "")

    def test_file_object_attachment_is_saved_to_book_file(self):
        checksum = "a" * 64

        result = persist_imported_book(
            metadata=sample_metadata(),
            checksum=checksum,
            source_filename="upload.epub",
            book_file=ContentFile(b"epub bytes", name="upload.epub"),
        )

        self.assertTrue(result.book.book_file.name.startswith("books/aa/aa/"))
        self.assertTrue(result.book.book_file.name.endswith(".epub"))

    def test_non_file_book_file_is_rejected(self):
        with self.assertRaises(ValidationError):
            persist_imported_book(
                metadata=sample_metadata(),
                checksum="bad-book-file",
                book_file="not-a-file",
            )

    def test_transaction_rolls_back_related_rows_on_persistence_error(self):
        with self.assertRaises(IntegrityError):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum="rollback123",
            )

        self.assertFalse(Book.objects.filter(checksum="rollback123").exists())
        self.assertFalse(Author.objects.filter(name__in=["One", "Two"]).exists())


def sample_metadata(**overrides) -> ImportMetadata:
    values = {
        "title": "Sample Book",
        "sort_title": "Sample Book, The",
        "subtitle": "A Subtitle",
        "authors": [ImportAuthor(name="Sample Author", sort_name="Author, Sample", position=0)],
        "series": None,
        "language": "en",
        "publisher": "Example Press",
        "description": "Example description",
        "published_year": None,
        "published_month": None,
        "published_day": None,
        "published_date_precision": "",
        "tags": [],
        "identifiers": [],
    }
    values.update(overrides)
    return ImportMetadata(**values)
