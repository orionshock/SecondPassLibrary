from __future__ import annotations

from io import BytesIO
import hashlib
import zipfile

from django.test import TestCase

from library.groups.public_group import get_public_group
from library.imports.epub import EPUB_IMPORT_ERROR_MESSAGE, import_epub_file
from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
)
from library.models import (
    Book,
    BookAuthor,
    BookCatalogTag,
    BookGroupAssignment,
    BookIdentifier,
    BookSeries,
    CatalogTag,
)
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, minimal_epub_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class SingleEpubImportServiceTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_valid_minimal_epub_imports_book(self):
        result = import_epub_file(
            BytesIO(minimal_epub_bytes()),
            source_filename="sample.epub",
            actor=self.actor,
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.safe_message, "Successfully imported EPUB.")
        self.assertEqual(result.operator_detail, "")
        self.assertEqual(result.book.title, "Sample EPUB")
        self.assertEqual(result.book.file_format, Book.FILE_FORMAT_EPUB)
        self.assertEqual(result.source_label, "sample.epub")
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=result.book,
                group=get_public_group(),
                added_by=self.actor,
            ).exists()
        )

    def test_checksum_file_size_and_book_file_are_persisted(self):
        data = minimal_epub_bytes()

        result = import_epub_file(BytesIO(data), source_filename="Original Name.epub")

        self.assertEqual(result.book.checksum, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.book.file_size, len(data))
        self.assertTrue(result.book.book_file.name.endswith(".epub"))
        self.assertTrue(result.book.book_file.name.startswith(f"books/{result.book.checksum[:2]}/"))

    def test_duplicate_checksum_returns_duplicate_without_second_book(self):
        data = minimal_epub_bytes()

        first = import_epub_file(BytesIO(data), source_filename="first.epub")
        second = import_epub_file(BytesIO(data), source_filename="second.epub")

        self.assertEqual(second.status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(second.book, first.book)
        self.assertEqual(second.operator_detail, "")
        self.assertEqual(Book.objects.filter(checksum=first.book.checksum).count(), 1)

    def test_invalid_extension_fails_safely(self):
        result = import_epub_file(BytesIO(minimal_epub_bytes()), source_filename="sample.txt")

        self.assertEqual(result.status, IMPORT_STATUS_FAILED)
        self.assertNotEqual(result.status, "skipped")
        self.assertEqual(result.safe_message, "Unsupported import source.")
        self.assertIn("UnsupportedImportSourceError", result.operator_detail)
        self.assertFalse(Book.objects.exists())

    def test_malformed_epub_zip_fails_safely(self):
        result = import_epub_file(BytesIO(b"not a zip"), source_filename="bad.epub")

        self.assertEqual(result.status, IMPORT_STATUS_FAILED)
        self.assertNotEqual(result.status, "skipped")
        self.assertEqual(result.safe_message, EPUB_IMPORT_ERROR_MESSAGE)
        self.assertNotIn("SecondPassLibrary", result.safe_message)
        self.assertFalse(Book.objects.exists())

    def test_missing_epub_package_metadata_fails_safely(self):
        data = _epub_without_package()

        result = import_epub_file(BytesIO(data), source_filename="missing-package.epub")

        self.assertEqual(result.status, IMPORT_STATUS_FAILED)
        self.assertEqual(result.safe_message, EPUB_IMPORT_ERROR_MESSAGE)
        self.assertFalse(Book.objects.exists())

    def test_malformed_opf_xml_fails_safely(self):
        data = _epub_with_raw_opf("<package><metadata")

        result = import_epub_file(BytesIO(data), source_filename="malformed-opf.epub")

        self.assertEqual(result.status, IMPORT_STATUS_FAILED)
        self.assertEqual(result.safe_message, EPUB_IMPORT_ERROR_MESSAGE)

    def test_calibre_metadata_maps_through_import_dto_semantics(self):
        metadata_xml = """
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>The Test Book</dc:title>
          <dc:creator opf:file-as="Writer, Example">Example Writer</dc:creator>
          <dc:subject>Fantasy</dc:subject>
          <meta name="calibre:title_sort" content="Test Book, The"/>
          <meta name="calibre:series" content="Example Series"/>
          <meta name="calibre:series_index" content="2.75"/>
          <meta name="calibre:tags" content="Fantasy, Space Opera"/>
        </metadata>
        """

        result = import_epub_file(
            BytesIO(minimal_epub_bytes(metadata_xml=metadata_xml)),
            source_filename="calibre.epub",
        )

        self.assertEqual(result.book.sort_title, "Test Book, The")
        self.assertEqual(BookAuthor.objects.get(book=result.book).author.sort_name, "Writer, Example")
        self.assertEqual(BookSeries.objects.get(book=result.book).series.name, "Example Series")
        self.assertEqual(str(BookSeries.objects.get(book=result.book).series_index), "2.75")
        self.assertEqual(
            set(
                BookCatalogTag.objects.filter(book=result.book)
                .select_related("catalog_tag")
                .values_list("catalog_tag__normalized_name", flat=True)
            ),
            {"fantasy", "space opera"},
        )
        self.assertTrue(CatalogTag.objects.filter(normalized_name="fantasy").exists())

    def test_import_sanitizes_html_description_from_epub_metadata(self):
        metadata_xml = """
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Described Book</dc:title>
          <dc:description>&lt;p class="calibre"&gt;A &lt;strong&gt;rich&lt;/strong&gt; description&lt;/p&gt;&lt;script&gt;alert("no")&lt;/script&gt;</dc:description>
        </metadata>
        """

        result = import_epub_file(
            BytesIO(minimal_epub_bytes(metadata_xml=metadata_xml)),
            source_filename="described.epub",
        )

        self.assertEqual(
            result.book.description,
            "<p>A <strong>rich</strong> description</p>",
        )

    def test_identifier_conflict_returns_conflict_item_result(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing-book")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        metadata_xml = """
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                  xmlns:opf="http://www.idpf.org/2007/opf">
          <dc:title>Conflicting Identifier</dc:title>
          <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
        </metadata>
        """

        result = import_epub_file(
            BytesIO(minimal_epub_bytes(metadata_xml=metadata_xml)),
            source_filename="conflict.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_CONFLICT)
        self.assertEqual(result.book, existing_book)
        self.assertEqual(
            result.safe_message,
            "An identifier from this import already belongs to another book.",
        )

    def test_source_label_uses_safe_filename_only(self):
        result = import_epub_file(
            BytesIO(minimal_epub_bytes()),
            source_filename=r"C:\unsafe\path\label.epub",
        )

        self.assertEqual(result.source_label, "label.epub")


def _epub_without_package() -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/missing.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
    return out.getvalue()


def _epub_with_raw_opf(opf_xml: str) -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
        zf.writestr("OEBPS/content.opf", opf_xml)
    return out.getvalue()
