from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from typing import Any, cast

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from PIL import Image

from library.admin import BookAdmin
from library.models import Book

from tests.library.utils import IsolatedMediaRootMixin


class _DummySite(AdminSite):
    pass


def _png_upload(*, name: str = "cover.png", size: tuple[int, int] = (32, 40)):
    img = Image.new("RGB", size, color=(10, 20, 30))
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    # Minimal UploadedFile-like object: admin only needs .read() + .name (+ optional .size).
    return SimpleNamespace(name=name, size=len(bio.getvalue()), read=bio.read)


class BookAdminCoverTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = BookAdmin(Book, self.site)
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True, is_superuser=True
        )

    def test_admin_cover_upload_sets_cover_fields(self):
        book = Book.objects.create(title="T")
        request = self.factory.post("/admin/library/book/")
        request.user = self.staff

        upload = _png_upload(size=(21, 22))
        form = SimpleNamespace(cleaned_data={"cover_upload": upload, "clear_cover": False})

        self.admin.save_model(request, book, cast(Any, form), change=True)

        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "manual")
        self.assertEqual(book.cover_mime, "image/png")
        self.assertEqual(book.cover_width, 21)
        self.assertEqual(book.cover_height, 22)

    def test_admin_clear_cover_removes_file_and_metadata(self):
        book = Book.objects.create(title="T")
        request = self.factory.post("/admin/library/book/")
        request.user = self.staff

        upload = _png_upload(size=(10, 11))
        form_upload = SimpleNamespace(cleaned_data={"cover_upload": upload, "clear_cover": False})
        self.admin.save_model(request, book, cast(Any, form_upload), change=True)

        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        form_clear = SimpleNamespace(cleaned_data={"cover_upload": None, "clear_cover": True})
        self.admin.save_model(request, book, cast(Any, form_clear), change=True)

        book.refresh_from_db()
        self.assertFalse(bool(book.cover_file))
        self.assertEqual(book.cover_source, "")
        self.assertEqual(book.cover_mime, "")
        self.assertIsNone(book.cover_width)
        self.assertIsNone(book.cover_height)
