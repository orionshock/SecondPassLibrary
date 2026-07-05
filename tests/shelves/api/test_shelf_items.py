from __future__ import annotations

import pytest
from rest_framework import status

from library.cover_services import set_book_cover_from_bytes
from shelves.models import Shelf, ShelfItem
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_dict,
    response_data_dict,
    response_data_list,
)

pytestmark = [pytest.mark.integration]


class ShelfItemTests(BaseShelvesAPITest):
    def test_add_and_list_items_filters_by_access(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            )
        )
        shelf_id = response_data_dict(create)["id"]

        add_ok = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(add_ok.status_code, status.HTTP_201_CREATED)

        # Reader cannot add a book they cannot view.
        add_denied = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_hidden.id)},
                format="json",
            )
        )
        self.assertEqual(add_denied.status_code, status.HTTP_403_FORBIDDEN)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        self.assertEqual(items.status_code, status.HTTP_200_OK)
        results = response_data_list(items)
        self.assertEqual(len(results), 1)
        added_by = payload_dict(results[0], "added_by")
        self._assert_compact_user_payload(added_by, user=self.reader)

    def test_shelf_items_include_book_cover_url_when_present(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(create)["id"]

        set_book_cover_from_bytes(
            book=self.book_in_group, data=self._png_bytes(), source="manual"
        )

        add_ok = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(add_ok.status_code, status.HTTP_201_CREATED)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        self.assertEqual(items.status_code, status.HTTP_200_OK)
        results = response_data_list(items)
        self.assertEqual(len(results), 1)
        book = payload_dict(results[0], "book")
        self.assertIn("cover_url", book)
        self.assertIsInstance(book["cover_url"], str)
        self.assertTrue(str(book["cover_url"]).startswith("http://testserver/"))

    def test_item_patch_duplicate_position_canonicalizes_response_and_list(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(create)["id"]

        book_z = create_file_backed_book(title="Zulu", assign_public=False).book
        from library.groups.services import ensure_book_public_assignment

        ensure_book_public_assignment(book=book_z, added_by=None)
        book_a = create_file_backed_book(title="Alpha", assign_public=False).book
        ensure_book_public_assignment(book=book_a, added_by=None)

        add_z = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(book_z.id)},
                format="json",
            )
        )
        self.assertEqual(add_z.status_code, status.HTTP_201_CREATED)
        add_a = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(book_a.id)},
                format="json",
            )
        )
        self.assertEqual(add_a.status_code, status.HTTP_201_CREATED)
        item_a_id = response_data_dict(add_a)["id"]

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_a_id}/",
                data={"position": 0},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(patch)["position"], 0)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        results = response_data_list(items)
        self.assertEqual(
            [(row["book"]["title"], row["position"]) for row in results],
            [("Alpha", 0), ("Zulu", 1)],
        )

    def test_item_patch_position_moves_item_down_and_shifts_intervening_items(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(create)["id"]

        item_ids: dict[str, str] = {}
        from library.groups.services import ensure_book_public_assignment

        for title in ["A", "B", "C", "D"]:
            book = create_file_backed_book(title=title, assign_public=False).book
            ensure_book_public_assignment(book=book, added_by=None)
            added = assert_response(
                self.client.post(
                    f"/api/v1/shelves/{shelf_id}/items/",
                    data={"book": str(book.id)},
                    format="json",
                ),
            )
            self.assertEqual(added.status_code, status.HTTP_201_CREATED)
            item_ids[title] = str(response_data_dict(added)["id"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_ids['B']}/",
                data={"position": 3},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(patch)["position"], 3)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        results = response_data_list(items)
        self.assertEqual(
            [(row["book"]["title"], row["position"]) for row in results],
            [("A", 0), ("C", 1), ("D", 2), ("B", 3)],
        )

    def test_item_patch_move_canonicalizes_legacy_duplicates_before_swapping(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf = Shelf.objects.get(pk=response_data_dict(create)["id"])

        books = [
            create_file_backed_book(title=title, assign_public=False).book
            for title in ["Gamma", "Zulu", "Alpha", "Omega"]
        ]
        from library.groups.services import ensure_book_public_assignment

        for book in books:
            ensure_book_public_assignment(book=book, added_by=None)

        ShelfItem.objects.create(
            shelf=shelf, book=books[0], position=0, added_by=self.reader
        )
        target = ShelfItem.objects.create(
            shelf=shelf, book=books[1], position=1, added_by=self.reader
        )
        ShelfItem.objects.create(
            shelf=shelf, book=books[2], position=1, added_by=self.reader
        )
        ShelfItem.objects.create(
            shelf=shelf, book=books[3], position=3, added_by=self.reader
        )

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{target.id}/",
                data={"move": "up"},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(patch)["position"], 1)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))
        results = response_data_list(items)
        self.assertEqual(
            [(row["book"]["title"], row["position"]) for row in results],
            [("Gamma", 0), ("Zulu", 1), ("Alpha", 2), ("Omega", 3)],
        )
