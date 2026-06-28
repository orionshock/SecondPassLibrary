from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Any, cast

from django.contrib.auth.models import User
from PIL import Image
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from accounts.services import get_or_create_profile
from library.cover_services import set_book_cover_from_bytes
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import Author, LibraryGroup, LibraryGroupMembership, Series
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book


class AuthorSeriesPreviewBooksAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.manager = User.objects.create_user(username="manager", password="pw")
        ensure_user_public_membership(user=self.manager)
        profile = get_or_create_profile(user=self.manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="other", password="pw")
        ensure_user_public_membership(user=self.other)
        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.other, group=self.hidden_group)

        self.author = Author.objects.create(name="Author A")
        self.series = Series.objects.create(name="Series S")
        self.public_books = []
        for index in range(7):
            book = create_file_backed_book(
                title=f"Book {index:02d}",
                assign_public=False,
                book_fields={
                    "series": self.series,
                    "series_index": Decimal(str(index)),
                },
            ).book
            book.authors.add(self.author)
            ensure_book_public_assignment(book=book, added_by=None)
            self.public_books.append(book)

        image = Image.new("RGB", (10, 12), color=(9, 9, 9))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        set_book_cover_from_bytes(
            book=self.public_books[0],
            data=buffer.getvalue(),
            source="manual",
        )

        self.hidden_book = create_file_backed_book(
            title="A Hidden",
            assign_public=False,
            book_fields={
                "series": self.series,
                "series_index": Decimal("0"),
            },
        ).book
        self.hidden_book.authors.add(self.author)
        add_book_to_group(
            actor=self.manager,
            book=self.hidden_book,
            group=self.hidden_group,
        )

    def _login_reader(self):
        self.client.login(username="reader", password="pw")

    def _login_manager(self):
        self.client.login(username="manager", password="pw")

    def _preview_titles(self, row: dict[str, Any]) -> list[str]:
        return [book["title"] for book in cast(list[dict[str, Any]], row["preview_books"])]

    def _assert_preview_shape(self, preview: dict[str, Any]):
        self.assertEqual(set(preview.keys()), {"id", "title", "cover_url"})
        self.assertNotIn("file", preview)
        self.assertNotIn("download_url", preview)
        self.assertNotIn("authors", preview)
        self.assertNotIn("series", preview)
        self.assertNotIn("groups", preview)

    def test_author_list_omits_preview_books_without_opt_in(self):
        self._login_reader()

        response = cast(Response, self.client.get("/api/v1/library/authors/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        self.assertNotIn("preview_books", row)

    def test_author_list_false_opt_in_omits_preview_books(self):
        self._login_reader()

        response = cast(
            Response,
            self.client.get("/api/v1/library/authors/?include_preview_books=false"),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        self.assertNotIn("preview_books", row)

    def test_author_list_includes_capped_visible_preview_books_when_opted_in(self):
        self._login_reader()

        response = cast(
            Response,
            self.client.get("/api/v1/library/authors/?include_preview_books=true"),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        previews = cast(list[dict[str, Any]], row["preview_books"])
        self.assertEqual(len(previews), 6)
        self.assertEqual(
            self._preview_titles(row),
            ["Book 00", "Book 01", "Book 02", "Book 03", "Book 04", "Book 05"],
        )
        self.assertNotIn("A Hidden", self._preview_titles(row))
        self._assert_preview_shape(previews[0])
        self.assertIsInstance(previews[0]["cover_url"], str)
        self.assertTrue(str(previews[0]["cover_url"]).startswith("http://testserver/"))
        self.assertIsNone(previews[1]["cover_url"])

    def test_series_list_omits_preview_books_without_opt_in(self):
        self._login_reader()

        response = cast(Response, self.client.get("/api/v1/library/series/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        self.assertNotIn("preview_books", row)

    def test_series_list_includes_capped_visible_preview_books_when_opted_in(self):
        self._login_reader()

        response = cast(
            Response,
            self.client.get("/api/v1/library/series/?include_preview_books=true"),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        previews = cast(list[dict[str, Any]], row["preview_books"])
        self.assertEqual(len(previews), 6)
        self.assertEqual(
            self._preview_titles(row),
            ["Book 00", "Book 01", "Book 02", "Book 03", "Book 04", "Book 05"],
        )
        self.assertNotIn("A Hidden", self._preview_titles(row))
        self._assert_preview_shape(previews[0])

    def test_broad_role_preview_books_include_otherwise_hidden_books(self):
        self._login_manager()

        response = cast(
            Response,
            self.client.get("/api/v1/library/authors/?include_preview_books=true"),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = cast(dict[str, Any], paginated_results(response)[0])
        self.assertEqual(self._preview_titles(row)[0], "A Hidden")
        self.assertEqual(len(row["preview_books"]), 6)

    def test_author_detail_preview_books_are_opt_in(self):
        self._login_reader()

        plain = cast(Response, self.client.get(f"/api/v1/library/authors/{self.author.id}/"))
        opted_in = cast(
            Response,
            self.client.get(
                f"/api/v1/library/authors/{self.author.id}/?include_preview_books=true"
            ),
        )

        self.assertEqual(plain.status_code, status.HTTP_200_OK)
        self.assertNotIn("preview_books", cast(dict[str, Any], plain.data))
        self.assertEqual(opted_in.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], opted_in.data)
        self.assertEqual(len(payload["preview_books"]), 6)
        self.assertNotIn("A Hidden", self._preview_titles(payload))

    def test_series_detail_preview_books_are_opt_in(self):
        self._login_reader()

        plain = cast(Response, self.client.get(f"/api/v1/library/series/{self.series.id}/"))
        opted_in = cast(
            Response,
            self.client.get(
                f"/api/v1/library/series/{self.series.id}/?include_preview_books=true"
            ),
        )

        self.assertEqual(plain.status_code, status.HTTP_200_OK)
        self.assertNotIn("preview_books", cast(dict[str, Any], plain.data))
        self.assertEqual(opted_in.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], opted_in.data)
        self.assertEqual(len(payload["preview_books"]), 6)
        self.assertEqual(
            self._preview_titles(payload),
            ["Book 00", "Book 01", "Book 02", "Book 03", "Book 04", "Book 05"],
        )
