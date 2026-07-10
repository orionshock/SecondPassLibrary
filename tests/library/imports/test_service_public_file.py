from __future__ import annotations

import library.models as library_models
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase

from library.groups.public_group import get_public_group
from library.imports.services import persist_imported_book
from library.models import BookGroupAssignment
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata


class ImportPersistencePublicFileTests(ImportPersistenceFixtureMixin, TestCase):
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

        self.assertFalse(hasattr(library_models, "BookFile"))
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
