from __future__ import annotations

from io import BytesIO
from pathlib import Path
import warnings

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.test import AsyncClient, TestCase
from django.test.utils import override_settings

from PIL import Image

from accounts.models import UserWebSession
from library.catalog.serializers.books import book_cover_url
from library.cover_objects import (
    IMMUTABLE_COVER_CACHE_CONTROL,
    is_canonical_cover_storage_name,
    is_immutable_public_cover_path,
)
from library.cover_services import replace_book_cover
from library.imports.covers import validate_cover_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin
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

    def _set_cover(self, book, content: bytes) -> None:
        cover = validate_cover_bytes(content)
        assert cover is not None
        replace_book_cover(book=book, cover=cover, log_success=False)

    def test_debug_serves_cover_file_only(self):
        book = create_file_backed_book(title="Has Cover").book
        self._set_cover(book, self._png_bytes())
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        url = book.cover_file.url
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Cache-Control"], IMMUTABLE_COVER_CACHE_CONTROL)
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

    def _set_cover(self, book, content: bytes) -> None:
        cover = validate_cover_bytes(content)
        assert cover is not None
        replace_book_cover(book=book, cover=cover, log_success=False)

    def test_non_debug_direct_server_serves_cover_file(self):
        book = create_file_backed_book(title="Has Cover").book
        self._set_cover(book, self._png_bytes())
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        response = self.client.get(book.cover_file.url)

        self.assertTrue(is_canonical_cover_storage_name(book.cover_file.name))
        self.assertTrue(is_immutable_public_cover_path(book.cover_file.url))
        self.assertEqual(book_cover_url(book), book.cover_file.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], IMMUTABLE_COVER_CACHE_CONTROL)
        self.assertIn("Last-Modified", response)
        self.assertNotIn("ETag", response)
        self.assertNotIn("Expires", response)
        self.assertNotIn("Vary", response)
        response.close()

    def test_hashed_cover_is_public_and_query_strings_do_not_bust_identity(self):
        book = create_file_backed_book(title="Public Cover").book
        content = self._png_bytes()
        self._set_cover(book, content)
        book.refresh_from_db()

        response = self.client.get(f"{book.cover_file.url}?cache_bust=unnecessary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), content)
        self.assertEqual(response["Cache-Control"], IMMUTABLE_COVER_CACHE_CONTROL)
        response.close()

    def test_hashed_cover_response_does_not_vary_by_authenticated_session(self):
        book = create_file_backed_book(title="Session-independent Cover").book
        self._set_cover(book, self._png_bytes())
        book.refresh_from_db()
        get_user_model().objects.create_user(username="reader", password="pw")
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.get(book.cover_file.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], IMMUTABLE_COVER_CACHE_CONTROL)
        self.assertNotIn("Vary", response)
        response.close()

    def test_hashed_cover_conditional_get_keeps_immutable_policy(self):
        book = create_file_backed_book(title="Conditional Cover").book
        self._set_cover(book, self._png_bytes())
        book.refresh_from_db()
        initial = self.client.get(book.cover_file.url)
        last_modified = initial["Last-Modified"]
        initial.close()

        response = self.client.get(
            book.cover_file.url,
            HTTP_IF_MODIFIED_SINCE=last_modified,
        )

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response["Cache-Control"], IMMUTABLE_COVER_CACHE_CONTROL)

    def test_noncanonical_covers_are_not_served_or_cached_as_immutable(self):
        digest = "ab" * 32
        paths = (
            "default.png",
            f"aa/ab/{digest}.png",
            f"ab/ab/{digest[:-1]}.png",
            f"ab/ab/{digest}.gif",
            f"ab/ab/{'g' + digest[1:]}.png",
            f"ab/ab/{digest}.png/extra",
        )

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(f"/media/covers/{path}")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Cache-Control", response)

    def test_only_canonical_cover_paths_bypass_web_session_tracking(self):
        book = create_file_backed_book(title="Middleware Cover").book
        self._set_cover(book, self._png_bytes())
        book.refresh_from_db()
        get_user_model().objects.create_user(username="tracked-reader", password="pw")
        self.assertTrue(self.client.login(username="tracked-reader", password="pw"))
        UserWebSession.objects.all().delete()

        cover_response = self.client.get(book.cover_file.url)
        cover_response.close()
        self.assertFalse(UserWebSession.objects.exists())

        self.client.get("/media/covers/default.png")
        self.assertTrue(UserWebSession.objects.exists())
        UserWebSession.objects.all().delete()

        self.client.get("/media/books/aa/bb/private.epub")
        self.assertTrue(UserWebSession.objects.exists())

    async def test_non_debug_asgi_cover_uses_an_async_iterator(self):
        book = await sync_to_async(
            lambda: create_file_backed_book(title="ASGI Cover").book
        )()
        await sync_to_async(self._set_cover)(book, self._png_bytes())
        await book.arefresh_from_db()

        response = await AsyncClient().get(book.cover_file.url)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            content = b"".join([chunk async for chunk in response])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertTrue(response.is_async)
        self.assertEqual(content, self._png_bytes())
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertFalse(
            any("synchronous iterators" in str(item.message) for item in caught)
        )

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
