from __future__ import annotations

from django.test import TestCase

from library.imports.archives import MAX_OPF_SIDECAR_XML_BYTES
from library.imports.batches import import_zip_file
from library.imports.results import IMPORT_STATUS_DUPLICATE, IMPORT_STATUS_FAILED, IMPORT_STATUS_IMPORTED
from library.models import Book, BookIdentifier
from tests.library.imports.helpers import (
    metadata_xml,
    minimal_epub_bytes,
    sidecar_opf_xml,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ZipSidecarMetadataTests(IsolatedMediaRootMixin, TestCase):
    def test_sidecar_with_no_title_falls_back_to_epub_metadata(self):
        sidecar = """
        <package xmlns="http://www.idpf.org/2007/opf">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:creator>Sidecar Author</dc:creator>
          </metadata>
        </package>
        """

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", sidecar.encode()),
            ),
            source_filename="missing-title.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_sidecar_with_blank_title_falls_back_to_epub_metadata(self):
        sidecar = """
        <package xmlns="http://www.idpf.org/2007/opf">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:title>   </dc:title>
            <dc:creator>Sidecar Author</dc:creator>
          </metadata>
        </package>
        """

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", sidecar.encode()),
            ),
            source_filename="blank-title.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_sidecar_with_only_title_fully_replaces_epub_metadata(self):
        epub_metadata = """
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>EPUB Title</dc:title>
          <dc:creator>EPUB Author</dc:creator>
          <dc:subject>EPUB Tag</dc:subject>
          <meta name="calibre:series" content="EPUB Series"/>
        </metadata>
        """
        sidecar = """
        <package xmlns="http://www.idpf.org/2007/opf">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:title>Only Sidecar Title</dc:title>
          </metadata>
        </package>
        """

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=epub_metadata)),
                ("dir/metadata.opf", sidecar.encode()),
            ),
            source_filename="replace.zip",
        )

        book = result.items[0].book
        self.assertEqual(book.title, "Only Sidecar Title")
        self.assertFalse(book.authors.exists())
        self.assertFalse(book.catalog_tags.exists())
        self.assertFalse(hasattr(book, "book_series"))

    def test_malformed_sidecar_falls_back_to_epub_metadata(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", b"<package><metadata"),
            ),
            source_filename="bad-sidecar.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_oversized_sidecar_falls_back_to_epub_metadata(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", b"x" * (MAX_OPF_SIDECAR_XML_BYTES + 1)),
            ),
            source_filename="big-sidecar.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_duplicate_checksum_with_sidecar_does_not_refresh_metadata(self):
        data = minimal_epub_bytes(metadata_xml=metadata_xml("Original Title"))
        first = import_zip_file(
            zip_bytes(("book.epub", data)),
            source_filename="first.zip",
        )

        second = import_zip_file(
            zip_bytes(
                ("book.epub", data),
                ("metadata.opf", sidecar_opf_xml("Sidecar Refresh").encode()),
            ),
            source_filename="second.zip",
        )

        first.items[0].book.refresh_from_db()
        self.assertEqual(second.items[0].status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(first.items[0].book.title, "Original Title")

    def test_duplicate_checksum_with_conflicting_sidecar_identifier_returns_duplicate(self):
        data = minimal_epub_bytes(metadata_xml=metadata_xml("Original Title"))
        first = import_zip_file(
            zip_bytes(("book.epub", data)),
            source_filename="first.zip",
        )
        BookIdentifier.objects.create(
            book=Book.objects.create(title="Existing", checksum="existing-conflict-source"),
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )

        second = import_zip_file(
            zip_bytes(
                ("book.epub", data),
                (
                    "metadata.opf",
                    sidecar_opf_xml(
                        "Sidecar Conflict",
                        identifier="<dc:identifier opf:scheme=\"ISBN\">978-0-00-000001-1</dc:identifier>",
                    ).encode(),
                ),
            ),
            source_filename="duplicate-conflict.zip",
        )

        first.items[0].book.refresh_from_db()
        self.assertEqual(second.items[0].status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(first.items[0].book.title, "Original Title")

    def test_sidecar_identifier_shared_with_another_book_imports(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing-sidecar-conflict")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )

        result = import_zip_file(
            zip_bytes(
                ("book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("No Conflict"))),
                (
                    "metadata.opf",
                    sidecar_opf_xml(
                        "Sidecar Conflict",
                        identifier="<dc:identifier opf:scheme=\"ISBN\">978-0-00-000001-1</dc:identifier>",
                    ).encode(),
                ),
            ),
            source_filename="sidecar-conflict.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertNotEqual(result.items[0].book, existing_book)
        self.assertTrue(
            BookIdentifier.objects.filter(
                book=result.items[0].book,
                scheme=BookIdentifier.SCHEME_ISBN_13,
                normalized_value="9780000000011",
            ).exists()
        )

    def test_invalid_epub_still_fails_with_valid_sidecar(self):
        result = import_zip_file(
            zip_bytes(
                ("book.epub", b"not an epub"),
                ("metadata.opf", sidecar_opf_xml("Valid Sidecar").encode()),
            ),
            source_filename="invalid-epub.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_FAILED)
        self.assertFalse(Book.objects.exists())

    def test_sidecar_path_does_not_appear_in_safe_message_when_epub_import_fails(self):
        result = import_zip_file(
            zip_bytes(
                ("book.epub", b"not an epub"),
                ("metadata.opf", sidecar_opf_xml("Valid Sidecar").encode()),
            ),
            source_filename="invalid-epub.zip",
        )

        self.assertNotIn("metadata.opf", result.items[0].safe_message)
        self.assertNotIn("book.epub", result.items[0].safe_message)
