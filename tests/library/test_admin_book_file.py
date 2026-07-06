from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import zipfile
import importlib

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, set_urlconf

from library.admin import BookAdmin, BookFileAdmin, BookFileAdminForm
from library.book_file_services import repair_book_file_for_book
from library.models import Author, Book, BookFile
from reading.models import Annotation, ReadingSession
import secondpass.urls
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import (
    create_file_backed_book,
    create_fileless_book_for_integrity_edge_case,
)


class _DummySite(AdminSite):
    pass


ROOT = Path(__file__).resolve().parents[2]


def _reload_project_urls() -> None:
    clear_url_caches()
    set_urlconf(None)
    importlib.reload(secondpass.urls)


def _epub_bytes(label: str = "book") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", f"<container>{label}</container>")
    return buffer.getvalue()


class BookFileAdminUploadTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = BookFileAdmin(BookFile, self.site)
        self.book_admin = BookAdmin(Book, self.site)
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True, is_superuser=True
        )

    def test_admin_add_computes_checksum_before_file_storage(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Needs File", assign_public=False
        )
        epub_bytes = _epub_bytes("admin upload bytes")
        upload = SimpleUploadedFile(
            "Original Name.epub", epub_bytes, content_type="application/epub+zip"
        )
        form = BookFileAdminForm(
            data={"book": book.pk, "format": BookFile.FORMAT_EPUB},
            files={"file": upload},
        )
        self.assertTrue(form.is_valid(), form.errors)

        request = self.factory.post("/admin/library/bookfile/add/")
        request.user = self.staff
        obj = form.save(commit=False)
        self.admin.save_model(request, obj, form, change=False)

        book_file = BookFile.objects.get(book=book)
        checksum = hashlib.sha256(epub_bytes).hexdigest()
        self.assertEqual(book_file.checksum, checksum)
        self.assertEqual(book_file.file_size, len(epub_bytes))
        self.assertEqual(book_file.source_filename, "Original Name.epub")
        self.assertEqual(
            book_file.file.name,
            f"books/{checksum[:2]}/{checksum[2:4]}/{checksum}.epub",
        )

    def test_admin_add_rejects_duplicate_checksum(self):
        epub_bytes = _epub_bytes("same bytes")
        existing = create_file_backed_book(
            title="Existing", epub_bytes=epub_bytes, assign_public=False
        )
        book = create_fileless_book_for_integrity_edge_case(
            title="Duplicate Target", assign_public=False
        )
        upload = SimpleUploadedFile(
            "duplicate.epub", epub_bytes, content_type="application/epub+zip"
        )

        form = BookFileAdminForm(
            data={"book": book.pk, "format": BookFile.FORMAT_EPUB},
            files={"file": upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertEqual(BookFile.objects.count(), 1)
        self.assertEqual(BookFile.objects.get(), existing.book_file)

    def test_admin_add_rejects_book_that_already_has_file(self):
        existing = create_file_backed_book(title="Existing", assign_public=False)
        upload = SimpleUploadedFile(
            "another.epub",
            _epub_bytes("different bytes"),
            content_type="application/epub+zip",
        )

        form = BookFileAdminForm(
            data={"book": existing.book.pk, "format": BookFile.FORMAT_EPUB},
            files={"file": upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("book", form.errors)
        self.assertEqual(BookFile.objects.count(), 1)

    def test_admin_add_rejects_non_epub_zip_payload(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Invalid Upload", assign_public=False
        )
        upload = SimpleUploadedFile(
            "bad.epub", b"not a zip", content_type="application/epub+zip"
        )

        form = BookFileAdminForm(
            data={"book": book.pk, "format": BookFile.FORMAT_EPUB},
            files={"file": upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)

    def test_book_admin_exposes_file_status_and_repair_link(self):
        with override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True):
            _reload_project_urls()
            book = create_fileless_book_for_integrity_edge_case(
                title="Status", assign_public=False
            )

            self.assertEqual(self.book_admin.book_file_status(book), "No BookFile row")
            repair_link = str(self.book_admin.book_file_repair_link(book))
            self.assertIn("Repair stored EPUB", repair_link)
            self.assertIn('class="button"', repair_link)
            self.assertIn("font-weight: 600", repair_link)
        _reload_project_urls()

        epub_bytes = _epub_bytes("status")
        checksum = hashlib.sha256(epub_bytes).hexdigest()
        BookFile.objects.create(
            book=book,
            file=f"books/{checksum[:2]}/{checksum[2:4]}/{checksum}.epub",
            checksum=checksum,
            file_size=len(epub_bytes),
            source_filename="missing.epub",
        )

        self.assertEqual(
            self.book_admin.book_file_status(book),
            "BookFile row exists; stored file missing",
        )

    def test_book_admin_changelist_uses_focused_operator_columns(self):
        self.assertEqual(
            self.book_admin.list_display,
            [
                "title",
                "first_author",
                "series",
                "series_index",
                "book_file_repair_link",
                "created_at",
            ],
        )

    def test_book_admin_changelist_loads_column_width_styles(self):
        css_files = self.book_admin.media._css["all"]

        self.assertIn("admin/library/book_changelist.css", css_files)

        css = (
            ROOT / "library" / "static" / "admin" / "library" / "book_changelist.css"
        ).read_text(encoding="utf-8")
        self.assertIn("td.field-title", css)
        self.assertIn("td.field-first_author", css)
        self.assertIn("td.field-series", css)
        self.assertIn("text-overflow: ellipsis", css)
        self.assertIn("td.field-book_file_repair_link", css)
        self.assertIn("white-space: nowrap", css)

    def test_book_admin_first_author_uses_first_ordered_author_only(self):
        book = Book.objects.create(title="Authors")
        book.authors.add(
            Author.objects.create(name="Zed Author"),
            Author.objects.create(name="Ada Author"),
        )

        self.assertEqual(self.book_admin.first_author(book), "Ada Author")

        fileless_book = Book.objects.create(title="No Authors")
        self.assertEqual(self.book_admin.first_author(fileless_book), "-")

    def test_book_file_admin_download_link_is_action_button(self):
        existing = create_file_backed_book(title="Download", assign_public=False)

        download_link = str(self.admin.download_epub_link(existing.book_file))

        self.assertIn("Download EPUB", download_link)
        self.assertIn('class="button"', download_link)
        self.assertIn("font-weight: 600", download_link)

    def test_book_file_admin_exposes_repair_link_to_book_repair_flow(self):
        with override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True):
            _reload_project_urls()
            existing = create_file_backed_book(title="Repair", assign_public=False)

            repair_link = str(self.admin.repair_epub_link(existing.book_file))

            self.assertIn("Repair stored EPUB", repair_link)
            self.assertIn('class="button"', repair_link)
            self.assertIn("font-weight: 600", repair_link)
            self.assertIn(
                f"/admin/library/book/{existing.book.pk}/repair-file/",
                repair_link,
            )
            self.assertIn("repair_epub_link", self.admin.readonly_fields)
            self.assertIn(
                ("Download", {"fields": ("download_epub_link", "repair_epub_link")}),
                self.admin.change_fieldsets,
            )
        _reload_project_urls()

    def test_repair_creates_book_file_for_fileless_existing_book(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Needs Repair", assign_public=False
        )
        epub_bytes = _epub_bytes("new file")
        upload = SimpleUploadedFile(
            "repair.epub", epub_bytes, content_type="application/epub+zip"
        )
        book_id = book.id

        result = repair_book_file_for_book(book=book, upload=upload)

        book.refresh_from_db()
        book_file = BookFile.objects.get(book=book)
        self.assertTrue(result.created)
        self.assertEqual(book.id, book_id)
        self.assertEqual(result.book_file, book_file)
        self.assertEqual(book.title, "Needs Repair")
        self.assertEqual(book_file.checksum, hashlib.sha256(epub_bytes).hexdigest())
        self.assertEqual(book_file.file_size, len(epub_bytes))
        self.assertEqual(book_file.source_filename, "repair.epub")

    def test_repair_missing_file_updates_existing_row_and_preserves_annotation_reference(
        self,
    ):
        book = create_fileless_book_for_integrity_edge_case(
            title="Missing File", assign_public=False
        )
        epub_bytes = _epub_bytes("restored")
        checksum = hashlib.sha256(epub_bytes).hexdigest()
        book_file = BookFile.objects.create(
            book=book,
            file=f"books/{checksum[:2]}/{checksum[2:4]}/{checksum}.epub",
            checksum=checksum,
            file_size=123,
            source_filename="lost.epub",
        )
        session = ReadingSession.objects.create(user=self.staff, book=book)
        annotation = Annotation.objects.create(
            session=session,
            book=book,
            book_file=book_file,
            anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK,
            selector_value="epubcfi(/6/2)",
        )
        upload = SimpleUploadedFile(
            "restored.epub", epub_bytes, content_type="application/epub+zip"
        )

        result = repair_book_file_for_book(book=book, upload=upload)

        book_file.refresh_from_db()
        annotation.refresh_from_db()
        self.assertFalse(result.created)
        self.assertEqual(result.book_file.pk, book_file.pk)
        self.assertEqual(annotation.book_file_id, book_file.pk)
        self.assertEqual(book_file.checksum, checksum)
        self.assertEqual(book_file.file_size, len(epub_bytes))
        self.assertEqual(book_file.source_filename, "restored.epub")
        self.assertTrue(book_file.file.storage.exists(book_file.file.name))

    def test_repair_rejects_checksum_mismatch_by_default_when_old_checksum_exists(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Mismatch", assign_public=False
        )
        book_file = BookFile.objects.create(
            book=book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="lost.epub",
        )
        upload = SimpleUploadedFile(
            "different.epub",
            _epub_bytes("different"),
            content_type="application/epub+zip",
        )

        with self.assertRaisesMessage(
            Exception,
            "Uploaded EPUB checksum does not match the existing BookFile checksum.",
        ):
            repair_book_file_for_book(book=book, upload=upload)

        book_file.refresh_from_db()
        self.assertEqual(book_file.checksum, "a" * 64)

    def test_repair_allows_checksum_mismatch_with_explicit_override(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Override", assign_public=False
        )
        book_file = BookFile.objects.create(
            book=book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="lost.epub",
        )
        epub_bytes = _epub_bytes("different")
        upload = SimpleUploadedFile(
            "different.epub", epub_bytes, content_type="application/epub+zip"
        )

        result = repair_book_file_for_book(
            book=book,
            upload=upload,
            allow_checksum_mismatch=True,
        )

        book_file.refresh_from_db()
        self.assertFalse(result.created)
        self.assertEqual(result.book_file.pk, book_file.pk)
        self.assertEqual(book_file.checksum, hashlib.sha256(epub_bytes).hexdigest())

    def test_repair_blocks_replacement_when_existing_file_is_present_by_default(self):
        existing = create_file_backed_book(
            title="Present",
            epub_bytes=_epub_bytes("present"),
            assign_public=False,
        )
        upload = SimpleUploadedFile(
            "replacement.epub",
            _epub_bytes("replacement"),
            content_type="application/epub+zip",
        )

        with self.assertRaisesMessage(
            Exception,
            "This book already has a stored EPUB file. Confirm replacement to continue.",
        ):
            repair_book_file_for_book(
                book=existing.book,
                upload=upload,
                allow_checksum_mismatch=True,
            )

    def test_repair_replaces_existing_present_file_only_with_explicit_override(self):
        existing = create_file_backed_book(
            title="Replace",
            epub_bytes=_epub_bytes("old"),
            assign_public=False,
        )
        book_file_id = existing.book_file.pk
        epub_bytes = _epub_bytes("new")
        upload = SimpleUploadedFile(
            "new.epub", epub_bytes, content_type="application/epub+zip"
        )

        result = repair_book_file_for_book(
            book=existing.book,
            upload=upload,
            replace_existing_file=True,
            allow_checksum_mismatch=True,
        )

        existing.book_file.refresh_from_db()
        self.assertFalse(result.created)
        self.assertEqual(existing.book_file.pk, book_file_id)
        self.assertEqual(
            existing.book_file.checksum, hashlib.sha256(epub_bytes).hexdigest()
        )
        self.assertEqual(existing.book.title, "Replace")
