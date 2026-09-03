from __future__ import annotations

from django.test import TestCase

from library.imports.services import IMPORT_STATUS_IMPORTED, persist_imported_book
from library.models import Book
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata


class ImportPersistenceBookFieldTests(ImportPersistenceFixtureMixin, TestCase):
    def test_persists_basic_book_fields_from_dto(self):
        result = persist_imported_book(
            metadata=sample_metadata(),
            checksum="abc123",
            file_size=1234,
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

    def test_sanitizes_imported_description_before_persistence(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                description=(
                    '<p class="calibre">Allowed <em>structure</em></p>'
                    '<script>alert("no")</script><img src="external">'
                )
            ),
            checksum="sanitized-description",
        )

        self.assertEqual(
            result.book.description,
            "<p>Allowed <em>structure</em></p>",
        )

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
