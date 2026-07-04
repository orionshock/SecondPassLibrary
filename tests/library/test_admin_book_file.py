from __future__ import annotations

import hashlib

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from library.admin import BookFileAdmin, BookFileAdminForm
from library.models import BookFile
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import (
    create_file_backed_book,
    create_fileless_book_for_integrity_edge_case,
)


class _DummySite(AdminSite):
    pass


class BookFileAdminUploadTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = BookFileAdmin(BookFile, self.site)
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True, is_superuser=True
        )

    def test_admin_add_computes_checksum_before_file_storage(self):
        book = create_fileless_book_for_integrity_edge_case(
            title="Needs File", assign_public=False
        )
        epub_bytes = b"admin upload bytes"
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
        existing = create_file_backed_book(
            title="Existing", epub_bytes=b"same bytes", assign_public=False
        )
        book = create_fileless_book_for_integrity_edge_case(
            title="Duplicate Target", assign_public=False
        )
        upload = SimpleUploadedFile(
            "duplicate.epub", b"same bytes", content_type="application/epub+zip"
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
            "another.epub", b"different bytes", content_type="application/epub+zip"
        )

        form = BookFileAdminForm(
            data={"book": existing.book.pk, "format": BookFile.FORMAT_EPUB},
            files={"file": upload},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("book", form.errors)
        self.assertEqual(BookFile.objects.count(), 1)
