from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase

from library.groups.public_group import get_public_group
from library.imports.batches import import_zip_file
from library.imports.results import (
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_SKIPPED,
)
from library.models import Book, BookGroupAssignment, BookIdentifier, LibraryGroupMembership
from library.queries import visible_books_for_user
from tests.library.imports.helpers import (
    ImportPersistenceFixtureMixin,
    metadata_xml,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ZipImportServiceTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_valid_zip_with_one_epub_imports_one_book(self):
        result = import_zip_file(
            zip_bytes(("nested/sample.epub", minimal_epub_bytes())),
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
        self.assertTrue(result.items[0].book.book_file.name)

    def test_batch_counts_imported_items(self):
        result = import_zip_file(
            zip_bytes(
                ("one.epub", minimal_epub_bytes(metadata_xml=metadata_xml("One"))),
                ("two.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Two"))),
            ),
            source_filename="books.zip",
        )

        self.assertEqual(result.total_found, 2)
        self.assertEqual(result.imported_count, 2)
        self.assertEqual(result.failed_count, 0)

    def test_planner_skipped_item_results_are_included(self):
        result = import_zip_file(
            zip_bytes(("dir/book.epub", b"a"), ("dir/./book.epub", b"b")),
            source_filename="colliding.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_SKIPPED)
        self.assertEqual(result.items[0].source_label, "book.epub")
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.imported_count, 0)

    def test_duplicate_checksum_in_zip_becomes_duplicate_item(self):
        data = minimal_epub_bytes()

        result = import_zip_file(
            zip_bytes(("first.epub", data), ("second.epub", data)),
            source_filename="duplicates.zip",
        )

        self.assertEqual([item.status for item in result.items], [IMPORT_STATUS_IMPORTED, IMPORT_STATUS_DUPLICATE])
        self.assertEqual(Book.objects.count(), 1)

    def test_shared_identifier_in_zip_imports_new_book(self):
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
          <dc:title>Shared Identifier</dc:title>
          <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
        </metadata>
        """

        result = import_zip_file(
            zip_bytes(("shared.epub", minimal_epub_bytes(metadata_xml=metadata_xml))),
            source_filename="shared.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertNotEqual(result.items[0].book, existing_book)
        self.assertEqual(Book.objects.count(), 2)

    def test_invalid_epub_member_fails_and_other_members_continue(self):
        result = import_zip_file(
            zip_bytes(
                ("bad.epub", b"not an epub"),
                ("good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
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
        self.assertIn("invalid or unsupported", result.items[0].safe_message)
        self.assertIn("try again", result.items[0].safe_message)
        self.assertFalse(Book.objects.exists())

    def test_zero_epub_zip_returns_empty_batch(self):
        result = import_zip_file(
            zip_bytes(("notes.txt", b"notes"), ("metadata.opf", b"opf")),
            source_filename="empty.zip",
        )

        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.items, [])
        self.assertFalse(Book.objects.exists())

    def test_discovered_count_comes_from_planner(self):
        result = import_zip_file(
            zip_bytes(("book.epub", minimal_epub_bytes()), ("notes.txt", b"notes")),
            source_filename="single.zip",
        )

        self.assertEqual(result.discovered_count, 1)
        self.assertEqual(result.total_found, 1)

    def test_backslash_member_path_imports_from_original_archive_member(self):
        result = import_zip_file(
            zip_bytes((r"dir\book.epub", minimal_epub_bytes())),
            source_filename="backslash.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].source_label, "book.epub")
        self.assertEqual(Book.objects.count(), 1)

    def test_actor_flows_to_public_assignment(self):
        result = import_zip_file(
            zip_bytes(("book.epub", minimal_epub_bytes())),
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

    def test_dot_segment_member_path_imports_from_original_archive_member(self):
        result = import_zip_file(
            zip_bytes(("dir/./book.epub", minimal_epub_bytes())),
            source_filename="dot-segment.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(Book.objects.count(), 1)

class ZipImportCacheInvalidationTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TransactionTestCase,
):
    def test_zip_import_publishes_complete_batch_to_cached_visibility(self):
        cache.clear()
        reader = get_user_model().objects.create_user(username="reader")
        LibraryGroupMembership.objects.create(user=reader, group=get_public_group())
        self.assertEqual(list(visible_books_for_user(reader)), [])

        result = import_zip_file(
            zip_bytes(
                ("one.epub", minimal_epub_bytes(metadata_xml=metadata_xml("One"))),
                ("two.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Two"))),
            ),
            source_filename="books.zip",
        )

        self.assertEqual(result.imported_count, 2)
        self.assertEqual(
            set(visible_books_for_user(reader).values_list("title", flat=True)),
            {"One", "Two"},
        )
