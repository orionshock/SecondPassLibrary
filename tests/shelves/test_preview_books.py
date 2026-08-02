from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.groups.memberships import ensure_user_public_membership
from library.groups.book_assignments import add_book_to_group, ensure_book_public_assignment
from library.models import LibraryGroup
from library.queries import invalidate_visible_books_cache
from shelves.models import Shelf, ShelfItem
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_list,
    response_data_dict,
    response_data_list,
)

User = get_user_model()


class ShelfPreviewBooksAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.owner = User.objects.create_superuser(
            username="owner",
            email="owner@example.com",
            password="pw",
        )
        ensure_user_public_membership(user=self.owner)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")

        self.shelf = Shelf.objects.create(
            name="Preview Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )

        self.hidden_book = create_file_backed_book(
            title="Hidden 00", assign_public=False
        ).book
        add_book_to_group(
            actor=self.owner, book=self.hidden_book, group=self.hidden_group
        )
        ShelfItem.objects.create(
            shelf=self.shelf,
            book=self.hidden_book,
            position=0,
            added_by=self.reader,
        )

        self.visible_books = []
        for index in range(25):
            book = create_file_backed_book(
                title=f"Visible {index:02d}",
                assign_public=False,
            ).book
            ensure_book_public_assignment(book=book, added_by=None)
            self.visible_books.append(book)
            ShelfItem.objects.create(
                shelf=self.shelf,
                book=book,
                position=index + 1,
                added_by=self.reader,
            )
        invalidate_visible_books_cache()

    def _results(self, response: Response) -> list[Any]:
        return response_data_list(response)

    def test_shelf_list_and_detail_preview_books_are_opt_in(self):
        self.client.login(username="reader", password="pw")

        list_default = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_default.status_code, status.HTTP_200_OK)
        default_row = next(
            row
            for row in self._results(list_default)
            if row["id"] == str(self.shelf.id)
        )
        self.assertNotIn("preview_books", default_row)

        detail_default = assert_response(
            self.client.get(f"/api/v1/shelves/{self.shelf.id}/")
        )
        self.assertEqual(detail_default.status_code, status.HTTP_200_OK)
        self.assertNotIn("preview_books", response_data_dict(detail_default))

        list_preview = assert_response(
            self.client.get("/api/v1/shelves/?include_preview_books=true"),
        )
        self.assertEqual(list_preview.status_code, status.HTTP_200_OK)
        preview_row = next(
            row
            for row in self._results(list_preview)
            if row["id"] == str(self.shelf.id)
        )
        self.assertIn("preview_books", preview_row)

        detail_preview = assert_response(
            self.client.get(
                f"/api/v1/shelves/{self.shelf.id}/?include_preview_books=true"
            ),
        )
        self.assertEqual(detail_preview.status_code, status.HTTP_200_OK)
        self.assertIn("preview_books", response_data_dict(detail_preview))

    def test_shelf_preview_books_shape_cap_order_and_visibility(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(
                f"/api/v1/shelves/{self.shelf.id}/?include_preview_books=true"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previews = payload_list(response_data_dict(response), "preview_books")

        self.assertEqual(len(previews), 6)
        self.assertEqual(
            [row["title"] for row in previews],
            [f"Visible {index:02d}" for index in range(6)],
        )
        self.assertNotIn("Hidden 00", {row["title"] for row in previews})
        for row in previews:
            self.assertEqual(set(row.keys()), {"id", "title", "cover_url"})
            self.assertIsNone(row["cover_url"])
            self.assertNotIn("download_url", row)

    def test_shelf_preview_limit_contract_applies_to_list_and_detail(self):
        self.client.login(username="reader", password="pw")
        list_url = "/api/v1/shelves/"
        detail_url = f"/api/v1/shelves/{self.shelf.id}/"

        for limit in (1, 6, 12, 24):
            with self.subTest(limit=limit):
                response = assert_response(
                    self.client.get(list_url, {"preview_limit": str(limit)})
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                row = next(
                    row for row in self._results(response)
                    if row["id"] == str(self.shelf.id)
                )
                self.assertEqual(len(row["preview_books"]), limit)
                self.assertEqual(row["item_count"], 25)

        detail = assert_response(
            self.client.get(detail_url, {"preview_limit": "12"})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_data_dict(detail)["preview_books"]), 12)
        self.assertEqual(response_data_dict(detail)["item_count"], 25)

        for url in (list_url, detail_url):
            with self.subTest(url=url):
                disabled = assert_response(
                    self.client.get(url, {"preview_limit": "0"})
                )
                payload = response_data_dict(disabled)
                row = (
                    response_data_list(disabled)[0]
                    if "results" in payload
                    else payload
                )
                self.assertNotIn("preview_books", row)

    def test_shelf_preview_limit_rejects_invalid_queries(self):
        self.client.login(username="reader", password="pw")
        url = "/api/v1/shelves/"
        for value in ("-1", "invalid", "25", "01", "+1"):
            with self.subTest(value=value):
                response = assert_response(
                    self.client.get(url, {"preview_limit": value})
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(set(response_data_dict(response)), {"preview_limit"})

        repeated = assert_response(
            self.client.get(f"{url}?preview_limit=1&preview_limit=2")
        )
        contradictory = assert_response(
            self.client.get(
                url,
                {"include_preview_books": "false", "preview_limit": "1"},
            )
        )
        self.assertEqual(repeated.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response_data_dict(repeated)), {"preview_limit"})
        self.assertEqual(contradictory.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response_data_dict(contradictory)), {"preview_limit"})

    def test_preview_limit_does_not_apply_to_full_shelf_items(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(
                f"/api/v1/shelves/{self.shelf.id}/items/",
                {"preview_limit": "invalid", "page_size": "2"},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(response)["count"], 25)
        self.assertEqual(len(response_data_list(response)), 2)
