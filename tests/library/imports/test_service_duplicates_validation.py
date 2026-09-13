from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from library.catalog.tag_services import resolve_catalog_tag
from library.imports.dto import ImportAuthor, ImportTag
from library.imports.services import (
    IMPORT_STATUS_DUPLICATE,
    persist_imported_book,
)
from library.models import Author, Book, BookCatalogTag
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ImportPersistenceDuplicateValidationTests(
    IsolatedMediaRootMixin, ImportPersistenceFixtureMixin, TestCase
):
    def test_duplicate_checksum_returns_duplicate_without_second_book(self):
        existing = Book.objects.create(title="Existing", checksum="duplicate123")

        result = persist_imported_book(metadata=sample_metadata(), checksum="duplicate123")

        self.assertEqual(result.status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(result.book, existing)
        self.assertEqual(Book.objects.filter(checksum="duplicate123").count(), 1)

    def test_duplicate_checksum_does_not_refresh_catalog_tags(self):
        existing = Book.objects.create(title="Existing", checksum="duplicate-tags")
        original_tag = resolve_catalog_tag("Original")
        BookCatalogTag.objects.create(book=existing, catalog_tag=original_tag)

        result = persist_imported_book(
            metadata=sample_metadata(
                tags=[ImportTag(name="Replacement", sort_name="Replacement", normalized_name="replacement")]
            ),
            checksum="duplicate-tags",
        )

        self.assertEqual(result.status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(list(existing.catalog_tags.values_list("name", flat=True)), ["Original"])

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

    def test_attachment_save_failure_removes_acquired_epub(self):
        checksum = "b" * 64
        expected_name = f"books/bb/bb/{checksum}.epub"
        original_save = Book.save

        class AttachmentSaveFailure(RuntimeError):
            pass

        def fail_attachment_save(instance, *args, **kwargs):
            if kwargs.get("update_fields") == ["book_file", "updated_at"]:
                raise AttachmentSaveFailure
            return original_save(instance, *args, **kwargs)

        with (
            patch.object(Book, "save", new=fail_attachment_save),
            self.assertRaises(AttachmentSaveFailure),
        ):
            persist_imported_book(
                metadata=sample_metadata(),
                checksum=checksum,
                book_file=ContentFile(b"epub bytes", name="upload.epub"),
            )

        storage = Book._meta.get_field("book_file").storage
        self.assertFalse(Book.objects.filter(checksum=checksum).exists())
        self.assertFalse(storage.exists(expected_name))

    def test_late_failure_removes_new_epub_as_database_state_rolls_back(self):
        checksum = "c" * 64

        with self.assertRaises(IntegrityError):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum=checksum,
                book_file=ContentFile(b"epub bytes", name="upload.epub"),
            )

        self.assertFalse(Book.objects.filter(checksum=checksum).exists())
        self.assertFalse(Author.objects.filter(name__in=["One", "Two"]).exists())
        self.assertFalse(
            (Path(self._media_root) / f"books/cc/cc/{checksum}.epub").exists()
        )

    def test_late_failure_preserves_preexisting_referenced_storage_object(self):
        checksum = "d" * 64
        expected_name = f"books/dd/dd/{checksum}.epub"
        referenced = Book.objects.create(title="Referenced", checksum="referenced")
        storage = Book._meta.get_field("book_file").storage
        storage.save(expected_name, ContentFile(b"existing bytes"))
        referenced.book_file.name = expected_name
        referenced.save(update_fields=["book_file", "updated_at"])

        with self.assertRaises(IntegrityError):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum=checksum,
                book_file=ContentFile(b"replacement bytes", name="upload.epub"),
            )

        self.assertTrue(storage.exists(expected_name))
        with storage.open(expected_name, "rb") as existing:
            self.assertEqual(existing.read(), b"existing bytes")

    def test_late_failure_preserves_preexisting_unreferenced_storage_object(self):
        checksum = "f" * 64
        expected_name = f"books/ff/ff/{checksum}.epub"
        storage = Book._meta.get_field("book_file").storage
        storage.save(expected_name, ContentFile(b"existing bytes"))

        with self.assertRaises(IntegrityError):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum=checksum,
                book_file=ContentFile(b"replacement bytes", name="upload.epub"),
            )

        self.assertFalse(Book.objects.filter(checksum=checksum).exists())
        self.assertTrue(storage.exists(expected_name))
        with storage.open(expected_name, "rb") as existing:
            self.assertEqual(existing.read(), b"existing bytes")

    def test_new_epub_is_preserved_when_an_existing_book_references_its_name(self):
        checksum = "1" * 64
        expected_name = f"books/11/11/{checksum}.epub"
        referenced = Book.objects.create(title="Referenced", checksum="referenced")
        referenced.book_file.name = expected_name
        referenced.save(update_fields=["book_file", "updated_at"])
        storage = Book._meta.get_field("book_file").storage

        with self.assertRaises(IntegrityError):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum=checksum,
                book_file=ContentFile(b"epub bytes", name="upload.epub"),
            )

        self.assertTrue(storage.exists(expected_name))

    def test_cleanup_failure_does_not_mask_original_import_failure(self):
        checksum = "e" * 64
        storage = Book._meta.get_field("book_file").storage
        original_delete = storage.delete

        with (
            patch.object(
                storage, "delete", side_effect=OSError("private/storage/path")
            ),
            self.assertLogs("library.imports.services", level="WARNING") as logs,
            self.assertRaises(IntegrityError),
        ):
            persist_imported_book(
                metadata=sample_metadata(
                    authors=[
                        ImportAuthor(name="One", sort_name="One", position=0),
                        ImportAuthor(name="Two", sort_name="Two", position=0),
                    ]
                ),
                checksum=checksum,
                book_file=ContentFile(b"epub bytes", name="upload.epub"),
            )

        self.assertNotIn("private/storage/path", " ".join(logs.output))
        self.assertFalse(Book.objects.filter(checksum=checksum).exists())
        self.assertIn(
            "action=new_epub_rollback_cleanup",
            " ".join(logs.output),
        )
        # Clean the deliberately orphaned test fixture without exercising product code.
        original_delete(f"books/ee/ee/{checksum}.epub")
