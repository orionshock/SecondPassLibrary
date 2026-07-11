from __future__ import annotations

from io import BytesIO
import zipfile

import library.models as library_models
from django.test import TestCase

from library.groups.public_group import get_public_group
from library.imports.batches import import_zip_file
from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_SKIPPED,
)
from library.models import Book, BookGroupAssignment, BookIdentifier
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, minimal_epub_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ZipImportServiceTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_valid_zip_with_one_epub_imports_one_book(self):
        result = import_zip_file(
            _zip_bytes(("nested/sample.epub", minimal_epub_bytes())),
            source_filename="upload.zip",
            actor=self.actor,
        )

        self.assertEqual(result.source_type, "zip")
        self.assertEqual(result.source_label, "upload.zip")
        self.assertEqual(result.total_found, 1)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].source_label, "sample.epub")
        self.assertEqual(Book.objects.count(), 1)

    def test_batch_counts_imported_items(self):
        result = import_zip_file(
            _zip_bytes(
                ("one.epub", minimal_epub_bytes(metadata_xml=_metadata_xml("One"))),
                ("two.epub", minimal_epub_bytes(metadata_xml=_metadata_xml("Two"))),
            ),
            source_filename="books.zip",
        )

        self.assertEqual(result.total_found, 2)
        self.assertEqual(result.imported_count, 2)
        self.assertEqual(result.failed_count, 0)

    def test_planner_skipped_item_results_are_included(self):
        result = import_zip_file(
            _zip_bytes(("dir/book.epub", b"a"), ("dir/./book.epub", b"b")),
            source_filename="colliding.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_SKIPPED)
        self.assertEqual(result.items[0].source_label, "book.epub")
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.imported_count, 0)

    def test_duplicate_checksum_in_zip_becomes_duplicate_item(self):
        data = minimal_epub_bytes()

        result = import_zip_file(
            _zip_bytes(("first.epub", data), ("second.epub", data)),
            source_filename="duplicates.zip",
        )

        self.assertEqual([item.status for item in result.items], [IMPORT_STATUS_IMPORTED, IMPORT_STATUS_DUPLICATE])
        self.assertEqual(Book.objects.count(), 1)

    def test_identifier_conflict_in_zip_becomes_conflict_item(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing-conflict-book")
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

        result = import_zip_file(
            _zip_bytes(("conflict.epub", minimal_epub_bytes(metadata_xml=metadata_xml))),
            source_filename="conflict.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_CONFLICT)
        self.assertEqual(result.items[0].book, existing_book)
        self.assertEqual(Book.objects.count(), 1)

    def test_invalid_epub_member_fails_and_other_members_continue(self):
        result = import_zip_file(
            _zip_bytes(
                ("bad.epub", b"not an epub"),
                ("good.epub", minimal_epub_bytes(metadata_xml=_metadata_xml("Good"))),
            ),
            source_filename="mixed.zip",
        )

        self.assertEqual([item.status for item in result.items], [IMPORT_STATUS_FAILED, IMPORT_STATUS_IMPORTED])
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Book.objects.get().title, "Good")

    def test_invalid_zip_returns_failed_batch_item_safely(self):
        result = import_zip_file(BytesIO(b"not a zip"), source_filename=r"C:\unsafe\bad.zip")

        self.assertEqual(result.source_label, "bad.zip")
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.items[0].status, IMPORT_STATUS_FAILED)
        self.assertEqual(result.items[0].safe_message, "Invalid or unsupported ZIP archive.")
        self.assertFalse(Book.objects.exists())

    def test_zero_epub_zip_returns_empty_batch(self):
        result = import_zip_file(
            _zip_bytes(("notes.txt", b"notes"), ("metadata.opf", b"opf")),
            source_filename="empty.zip",
        )

        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.items, [])
        self.assertFalse(Book.objects.exists())

    def test_discovered_count_comes_from_planner(self):
        result = import_zip_file(
            _zip_bytes(("book.epub", minimal_epub_bytes()), ("notes.txt", b"notes")),
            source_filename="single.zip",
        )

        self.assertEqual(result.discovered_count, 1)
        self.assertEqual(result.total_found, 1)

    def test_backslash_member_path_imports_from_original_archive_member(self):
        result = import_zip_file(
            _zip_bytes((r"dir\book.epub", minimal_epub_bytes())),
            source_filename="backslash.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].source_label, "book.epub")
        self.assertEqual(Book.objects.count(), 1)

    def test_actor_flows_to_public_assignment(self):
        result = import_zip_file(
            _zip_bytes(("book.epub", minimal_epub_bytes())),
            source_filename="actor.zip",
            actor=self.actor,
        )

        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=result.items[0].book,
                group=get_public_group(),
                added_by=self.actor,
            ).exists()
        )

    def test_sidecar_opf_metadata_is_not_applied_yet(self):
        sidecar_xml = """
        <package xmlns="http://www.idpf.org/2007/opf">
          <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:title>Sidecar Title</dc:title>
          </metadata>
        </package>
        """

        result = import_zip_file(
            _zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=_metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", sidecar_xml.encode()),
            ),
            source_filename="sidecar.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "EPUB Title")
        self.assertFalse(Book.objects.filter(title="Sidecar Title").exists())

    def test_no_bookfile_model_or_object_appears(self):
        result = import_zip_file(
            _zip_bytes(("book.epub", minimal_epub_bytes())),
            source_filename="book.zip",
        )

        self.assertFalse(hasattr(library_models, "BookFile"))
        self.assertTrue(result.items[0].book.book_file.name)


def _zip_bytes(*entries: tuple[str, bytes]) -> BytesIO:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    out.seek(0)
    return out


def _metadata_xml(title: str) -> str:
    return f"""
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>{title}</dc:title>
      <dc:creator>Sample Author</dc:creator>
      <dc:language>en</dc:language>
    </metadata>
    """
