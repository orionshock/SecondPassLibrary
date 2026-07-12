from __future__ import annotations

import pytest
from rest_framework import status

from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import assert_response, response_data_dict, response_data_list


pytestmark = [pytest.mark.integration]


class ShelfBookFilterEndpointTests(BaseShelvesAPITest):
    def test_list_filter_book_does_not_leak_private_user_shelves(self):
        # Create a private user shelf for reader and add book_in_group.
        self.client.login(username="reader", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "P", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]
        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)

        # Other user can view the book (Public membership), but must not see reader's private shelf.
        self.client.logout()
        self.client.login(username="other", password="pw")
        list_resp = assert_response(
            self.client.get(f"/api/v1/shelves/?book={self.book_in_group.id}")
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_list(list_resp)
        self.assertNotIn(shelf_id, {r["id"] for r in results})

    def test_list_filter_book_includes_matched_item_id(self):
        self.client.login(username="reader", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "S", "owner_type": "user"},
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]

        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)
        item_id = response_data_dict(add)["id"]

        list_resp = assert_response(
            self.client.get(f"/api/v1/shelves/?book={self.book_public.id}")
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_list(list_resp)

        row = next((r for r in results if r.get("id") == shelf_id), None)
        self.assertIsNotNone(row)
        self.assertEqual(row.get("matched_item_id"), item_id)
