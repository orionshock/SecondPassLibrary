from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from library.file_repair import (
    ChecksumChangeConfirmationRequired,
    ChecksumCollisionError,
    ReplaceExistingConfirmationRequired,
    StoredEpubRepairError,
    repair_stored_epub,
)
from library.models import (
    Author,
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    LibraryGroup,
    Series,
)
from library.groups.book_assignments import add_book_to_group
from marginalia.models import Annotation, ReadingSession
from shelves.models import Shelf, ShelfItem
from tests.library.imports.helpers import minimal_epub_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import attach_test_cover, create_file_backed_book


def epub_bytes(title: str) -> bytes:
    return minimal_epub_bytes(
        metadata_xml=f"""
        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>{title}</dc:title>
          <dc:language>en</dc:language>
        </metadata>
        """
    )


class StoredEpubRepairTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_superuser(
            username="operator",
            password="pw",
        )
        self.original_data = epub_bytes("Original")
        self.book = create_file_backed_book(
            title="Repair Target",
            epub_bytes=self.original_data,
            source_filename="original.epub",
            assign_public=False,
        ).book

    def _upload(self, data, name="replacement.epub"):
        upload = BytesIO(data)
        upload.name = name
        return upload

    def _repair(self, data=None, **kwargs):
        return repair_stored_epub(
            book=self.book,
            uploaded_epub=self._upload(data or self.original_data),
            replace_existing=kwargs.pop("replace_existing", True),
            allow_checksum_change=kwargs.pop("allow_checksum_change", False),
            actor=self.operator,
            **kwargs,
        )

    def test_missing_stored_file_restoration_succeeds_without_replace_confirmation(self):
        old_name = self.book.book_file.name
        self.book.book_file.storage.delete(old_name)

        result = self._repair(replace_existing=False)

        self.book.refresh_from_db()
        self.assertTrue(self.book.book_file.storage.exists(self.book.book_file.name))
        self.assertTrue(result.restored_missing_file)
        self.assertFalse(result.replaced_existing_file)

    def test_existing_stored_file_requires_replace_confirmation(self):
        with self.assertRaises(ReplaceExistingConfirmationRequired):
            self._repair(replace_existing=False)

    def test_same_checksum_replacement_succeeds(self):
        old_name = self.book.book_file.name

        with self.captureOnCommitCallbacks(execute=True):
            result = self._repair()

        self.book.refresh_from_db()
        self.assertFalse(result.checksum_changed)
        self.assertTrue(result.replaced_existing_file)
        self.assertTrue(self.book.book_file.storage.exists(self.book.book_file.name))
        self.assertFalse(self.book.book_file.storage.exists(old_name))

    def test_changed_checksum_requires_explicit_confirmation_with_cfi_warning(self):
        changed = epub_bytes("Changed")

        with self.assertRaises(ChecksumChangeConfirmationRequired) as captured:
            self._repair(changed)

        self.assertIn("EPUB CFI anchors may no longer match", str(captured.exception))

    def test_changed_checksum_succeeds_when_confirmed(self):
        changed = epub_bytes("Changed")

        with self.assertLogs("library.file_repair", level="WARNING") as logs:
            result = self._repair(changed, allow_checksum_change=True)

        self.book.refresh_from_db()
        self.assertTrue(result.checksum_changed)
        self.assertEqual(self.book.checksum, result.new_checksum)
        self.assertIn("Accepted changed EPUB checksum", logs.output[0])

    def test_checksum_collision_with_another_book_is_rejected(self):
        collision_data = epub_bytes("Collision")
        create_file_backed_book(
            title="Other Book",
            epub_bytes=collision_data,
            source_filename="other.epub",
            assign_public=False,
        )

        with self.assertRaises(ChecksumCollisionError):
            self._repair(collision_data, allow_checksum_change=True)

    def test_invalid_or_non_epub_input_is_rejected(self):
        with self.assertRaises(StoredEpubRepairError):
            repair_stored_epub(
                book=self.book,
                uploaded_epub=self._upload(b"not an epub"),
                replace_existing=True,
                allow_checksum_change=True,
                actor=self.operator,
            )
        with self.assertRaises(StoredEpubRepairError):
            repair_stored_epub(
                book=self.book,
                uploaded_epub=self._upload(self.original_data, "book.txt"),
                replace_existing=True,
                allow_checksum_change=False,
                actor=self.operator,
            )

    def test_all_book_owned_file_fields_update_consistently(self):
        changed = epub_bytes("Changed fields")

        result = self._repair(changed, allow_checksum_change=True)

        self.book.refresh_from_db()
        self.assertEqual(self.book.file_format, "epub")
        self.assertEqual(self.book.checksum, result.new_checksum)
        self.assertEqual(self.book.file_size, len(changed))
        self.assertTrue(self.book.book_file.name.endswith(".epub"))
        self.assertTrue(self.book.book_file.storage.exists(self.book.book_file.name))

    def test_cover_catalog_and_reading_relationships_remain_unchanged(self):
        attach_test_cover(book=self.book)
        author = Author.objects.create(name="Author")
        series = Series.objects.create(name="Series")
        tag = CatalogTag.objects.create(
            name="Tag",
            normalized_name="tag",
            slug="tag",
        )
        group = LibraryGroup.objects.create(name="Room")
        BookAuthor.objects.create(book=self.book, author=author, position=0)
        BookSeries.objects.create(book=self.book, series=series, series_index="1")
        BookCatalogTag.objects.create(book=self.book, catalog_tag=tag)
        identifier = BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_OTHER,
            value="value",
            normalized_value="value",
        )
        add_book_to_group(book=self.book, group=group)
        shelf = Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.operator,
        )
        shelf_item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book,
            added_by=self.operator,
        )
        session = ReadingSession.objects.create(
            user=self.operator,
            book=self.book,
            progress_cfi="epubcfi(/6/2)",
            progress_location_label="Chapter 1",
            progress_updated_at=timezone.now(),
        )
        annotation = Annotation.objects.create(
            session=session,
            client_id="file-repair-preservation",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        snapshot = {
            "cover": self.book.cover_file.name,
            "authors": list(self.book.book_authors.values_list("id", flat=True)),
            "series": self.book.book_series.id,
            "tags": list(self.book.book_catalog_tags.values_list("id", flat=True)),
            "identifier": identifier.id,
            "groups": list(self.book.group_assignments.values_list("id", flat=True)),
            "shelf_item": shelf_item.id,
            "session": session.id,
            "progress_cfi": session.progress_cfi,
            "progress_location_label": session.progress_location_label,
            "progress_updated_at": session.progress_updated_at,
            "annotation": annotation.id,
        }

        self._repair(epub_bytes("Relationship safe"), allow_checksum_change=True)

        self.book.refresh_from_db()
        self.assertEqual(self.book.cover_file.name, snapshot["cover"])
        self.assertEqual(
            list(self.book.book_authors.values_list("id", flat=True)),
            snapshot["authors"],
        )
        self.assertEqual(self.book.book_series.id, snapshot["series"])
        self.assertEqual(
            list(self.book.book_catalog_tags.values_list("id", flat=True)),
            snapshot["tags"],
        )
        self.assertTrue(self.book.identifiers.filter(pk=snapshot["identifier"]).exists())
        self.assertEqual(
            list(self.book.group_assignments.values_list("id", flat=True)),
            snapshot["groups"],
        )
        self.assertTrue(self.book.shelf_items.filter(pk=snapshot["shelf_item"]).exists())
        session.refresh_from_db()
        self.assertTrue(
            self.book.marginalia_sessions.filter(pk=snapshot["session"]).exists()
        )
        self.assertEqual(session.progress_cfi, snapshot["progress_cfi"])
        self.assertEqual(
            session.progress_location_label,
            snapshot["progress_location_label"],
        )
        self.assertEqual(session.progress_updated_at, snapshot["progress_updated_at"])
        self.assertTrue(session.annotations.filter(pk=snapshot["annotation"]).exists())

    def test_staged_file_is_cleaned_and_original_remains_on_database_failure(self):
        original_name = self.book.book_file.name
        original_bytes = self.book.book_file.storage.open(original_name, "rb").read()
        before = {path for path in Path(self._media_root).rglob("*") if path.is_file()}

        with (
            patch("library.file_repair.Book.save", side_effect=IntegrityError("forced")),
            self.assertRaises(IntegrityError),
        ):
            self._repair(
                epub_bytes("Database failure"),
                allow_checksum_change=True,
            )

        after = {path for path in Path(self._media_root).rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        self.assertTrue(self.book.book_file.storage.exists(original_name))
        self.assertEqual(
            self.book.book_file.storage.open(original_name, "rb").read(),
            original_bytes,
        )

    def test_info_log_does_not_include_upload_basename(self):
        upload = self._upload(self.original_data, r"C:\private\secret\book.epub")

        with self.assertLogs("library.file_repair", level="INFO") as logs:
            result = repair_stored_epub(
                book=self.book,
                uploaded_epub=upload,
                replace_existing=True,
                allow_checksum_change=False,
                actor=self.operator,
            )

        self.assertNotIn("book.epub", logs.output[-1])
        self.assertNotIn("private", logs.output[-1])
        self.assertFalse(hasattr(result, "source_filename"))
