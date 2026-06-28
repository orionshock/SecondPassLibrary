from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any, cast

from django.contrib.auth.models import User
from PIL import Image
from rest_framework.test import APIRequestFactory, APITestCase

from library.catalog_serializers import BookPreviewSerializer
from library.cover_services import set_book_cover_from_bytes
from library.group_services import ensure_user_public_membership
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


class BookPreviewSerializerTest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.user)
        self.factory = APIRequestFactory()

    def _request(self):
        request = self.factory.get("/api/v1/library/books/")
        request.user = self.user
        return request

    def test_without_cover_uses_minimal_shape_with_null_cover_url(self):
        book = create_file_backed_book(title="No Cover", assign_public=False).book

        payload = cast(
            Mapping[str, Any],
            BookPreviewSerializer(book, context={"request": self._request()}).data,
        )

        self.assertEqual(set(payload.keys()), {"id", "title", "cover_url"})
        self.assertEqual(payload["id"], str(book.id))
        self.assertEqual(payload["title"], "No Cover")
        self.assertIsNone(payload["cover_url"])
        self.assertNotIn("file", payload)
        self.assertNotIn("download_url", payload)
        self.assertNotIn("authors", payload)
        self.assertNotIn("series", payload)
        self.assertNotIn("groups", payload)

    def test_with_cover_uses_absolute_cover_url_when_request_context_is_present(self):
        book = create_file_backed_book(title="Has Cover", assign_public=False).book
        image = Image.new("RGB", (10, 12), color=(9, 9, 9))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        set_book_cover_from_bytes(book=book, data=buffer.getvalue(), source="manual")

        payload = cast(
            Mapping[str, Any],
            BookPreviewSerializer(book, context={"request": self._request()}).data,
        )

        self.assertEqual(set(payload.keys()), {"id", "title", "cover_url"})
        self.assertEqual(payload["id"], str(book.id))
        self.assertEqual(payload["title"], "Has Cover")
        self.assertIsInstance(payload["cover_url"], str)
        self.assertTrue(str(payload["cover_url"]).startswith("http://testserver/"))
        self.assertNotIn("file", payload)
        self.assertNotIn("download_url", payload)
