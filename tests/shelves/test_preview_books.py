from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import LibraryGroup
from shelves.models import Shelf, ShelfItem
from tests.utils.books import create_file_backed_book

User = get_user_model()


class ShelfPreviewBooksAPITest(APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.owner = User.objects.create_superuser(username="owner", password="pw")
        ensure_user_public_membership(user=self.owner)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")

        self.shelf = Shelf.objects.create(
            name="Preview Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )

        self.hidden_book = create_file_backed_book(title="Hidden 00", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.hidden_book, group=self.hidden_group)
        ShelfItem.objects.create(
            shelf=self.shelf,
            book=self.hidden_book,
            position=0,
            added_by=self.reader,
        )

        self.visible_books = []
        for index in range(7):
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

    def _results(self, response: Response) -> list[dict[str, Any]]:
        payload = cast(Mapping[str, Any], response.data)
        return cast(list[dict[str, Any]], payload["results"])

    def test_shelf_list_and_detail_preview_books_are_opt_in(self):
        self.client.login(username="reader", password="pw")

        list_default = cast(Response, self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_default.status_code, status.HTTP_200_OK)
        default_row = next(row for row in self._results(list_default) if row["id"] == str(self.shelf.id))
        self.assertNotIn("preview_books", default_row)

        detail_default = cast(Response, self.client.get(f"/api/v1/shelves/{self.shelf.id}/"))
        self.assertEqual(detail_default.status_code, status.HTTP_200_OK)
        self.assertNotIn("preview_books", cast(Mapping[str, Any], detail_default.data))

        list_preview = cast(
            Response,
            self.client.get("/api/v1/shelves/?include_preview_books=true"),
        )
        self.assertEqual(list_preview.status_code, status.HTTP_200_OK)
        preview_row = next(row for row in self._results(list_preview) if row["id"] == str(self.shelf.id))
        self.assertIn("preview_books", preview_row)

        detail_preview = cast(
            Response,
            self.client.get(f"/api/v1/shelves/{self.shelf.id}/?include_preview_books=true"),
        )
        self.assertEqual(detail_preview.status_code, status.HTTP_200_OK)
        self.assertIn("preview_books", cast(Mapping[str, Any], detail_preview.data))

    def test_shelf_preview_books_shape_cap_order_and_visibility(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/shelves/{self.shelf.id}/?include_preview_books=true"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        previews = cast(list[dict[str, Any]], payload["preview_books"])

        self.assertEqual(len(previews), 6)
        self.assertEqual([row["title"] for row in previews], [f"Visible {index:02d}" for index in range(6)])
        self.assertNotIn("Hidden 00", {row["title"] for row in previews})
        for row in previews:
            self.assertEqual(set(row.keys()), {"id", "title", "cover_url"})
            self.assertIsNone(row["cover_url"])
            self.assertNotIn("download_url", row)
