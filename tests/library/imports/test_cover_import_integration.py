from __future__ import annotations

from io import BytesIO

import library.models as library_models
from django.test import TestCase

from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_IMPORTED,
)
from library.models import Book, BookIdentifier
from tests.library.imports.helpers import (
    epub_with_cover_bytes,
    image_bytes,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class EpubCoverImportIntegrationTests(IsolatedMediaRootMixin, TestCase):
    def test_duplicate_checksum_does_not_refresh_cover(self):
        data = epub_with_cover_bytes(cover_bytes=image_bytes("PNG"))
        first = import_epub_file(BytesIO(data), source_filename="first.epub")
        first.book.cover_file.delete(save=True)

        second = import_epub_file(BytesIO(data), source_filename="second.epub")
        first.book.refresh_from_db()

        self.assertEqual(second.status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(first.book.cover_file.name, "")

    def test_identifier_conflict_does_not_save_new_cover(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        metadata_xml = """
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                  xmlns:opf="http://www.idpf.org/2007/opf">
          <dc:title>Conflict</dc:title>
          <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
        </metadata>
        """

        result = import_epub_file(
            BytesIO(epub_with_cover_bytes(cover_bytes=image_bytes("PNG"), metadata_xml=metadata_xml)),
            source_filename="conflict.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_CONFLICT)
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(existing_book.cover_file.name, "")

    def test_zip_import_gets_cover_through_shared_epub_path(self):
        result = import_zip_file(
            zip_bytes(("book.epub", epub_with_cover_bytes(cover_bytes=image_bytes("PNG")))),
            source_filename="covers.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(Book.objects.get().cover_file.name)

    def test_no_bookfile_model_or_object_appears(self):
        result = import_epub_file(
            BytesIO(minimal_epub_bytes()),
            source_filename="sample.epub",
        )

        self.assertFalse(hasattr(library_models, "BookFile"))
        self.assertTrue(result.book.book_file.name)
