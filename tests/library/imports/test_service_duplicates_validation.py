from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from library.imports.dto import ImportAuthor
from library.imports.services import IMPORT_STATUS_DUPLICATE, persist_imported_book
from library.models import Author, Book
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata


class ImportPersistenceDuplicateValidationTests(ImportPersistenceFixtureMixin, TestCase):
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
