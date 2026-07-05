from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.test import TestCase
from django.test.utils import override_settings

from PIL import Image

from library.cover_services import set_book_cover_from_bytes
from tests.env.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


class CoverMediaServingSmokeTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self._override = override_settings(DEBUG=True)
        self._override.enable()

    def tearDown(self):
        self._override.disable()

    def _png_bytes(self) -> bytes:
        img = Image.new("RGB", (10, 12), color=(1, 2, 3))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_debug_serves_cover_file_only(self):
        book = create_file_backed_book(title="Has Cover").book
        set_book_cover_from_bytes(book=book, data=self._png_bytes(), source="manual")
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        url = book.cover_file.url
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        resp.close()

        private_dir = Path(self._media_root) / "books" / "aa" / "bb"
        private_dir.mkdir(parents=True)
        (private_dir / "private.epub").write_bytes(b"epub data")

        private_resp = self.client.get("/media/books/aa/bb/private.epub")
        self.assertEqual(private_resp.status_code, 404)

        other_resp = self.client.get("/media/anything-else.txt")
        self.assertEqual(other_resp.status_code, 404)


class DirectServerCoverServingTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self._override = override_settings(DEBUG=False)
        self._override.enable()

    def tearDown(self):
        self._override.disable()

    def _png_bytes(self) -> bytes:
        img = Image.new("RGB", (10, 12), color=(1, 2, 3))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_non_debug_direct_server_serves_cover_file(self):
        book = create_file_backed_book(title="Has Cover").book
        set_book_cover_from_bytes(book=book, data=self._png_bytes(), source="manual")
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        response = self.client.get(book.cover_file.url)

        self.assertEqual(response.status_code, 200)
        response.close()

    def test_non_debug_missing_cover_returns_404(self):
        response = self.client.get("/media/covers/aa/bb/missing.jpg")

        self.assertEqual(response.status_code, 404)

    def test_non_debug_does_not_serve_book_files_or_sibling_media(self):
        private_dir = Path(self._media_root) / "books" / "aa" / "bb"
        private_dir.mkdir(parents=True)
        (private_dir / "private.epub").write_bytes(b"epub data")

        response = self.client.get("/media/books/aa/bb/private.epub")

        self.assertEqual(response.status_code, 404)

    def test_non_debug_cover_route_rejects_traversal(self):
        response = self.client.get("/media/covers/../books/private.epub")

        self.assertEqual(response.status_code, 404)
