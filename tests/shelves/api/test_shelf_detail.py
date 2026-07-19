from __future__ import annotations

import pytest
from rest_framework import status

from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import (
    assert_response,
    payload_dict,
    response_data_dict,
    response_data_list,
)


pytestmark = [pytest.mark.integration]


class ShelfDetailEndpointTests(BaseShelvesAPITest):
    def test_list_and_detail_visibility_matrix_for_user_owned_shelves(self):
        self.client.login(username="reader", password="pw")
        private = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Reader Private", "owner_type": "user"},
                format="json",
            ),
        )
        self.assertEqual(private.status_code, status.HTTP_201_CREATED)
        private_id = response_data_dict(private)["id"]

        listed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Reader Listed",
                    "owner_type": "user",
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        self.assertEqual(listed.status_code, status.HTTP_201_CREATED)
        listed_id = response_data_dict(listed)["id"]
        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{listed_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
            )
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)

        owner_list = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(owner_list.status_code, status.HTTP_200_OK)
        owner_ids = {row["id"] for row in response_data_list(owner_list)}
        self.assertIn(private_id, owner_ids)
        self.assertIn(listed_id, owner_ids)
        owner_detail = assert_response(
            self.client.get(f"/api/v1/shelves/{private_id}/")
        )
        self.assertEqual(owner_detail.status_code, status.HTTP_200_OK)

        for username in ["other", "manager", "owner"]:
            self.client.logout()
            self.client.login(username=username, password="pw")
            list_resp = assert_response(self.client.get("/api/v1/shelves/"))
            self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
            ids = {row["id"] for row in response_data_list(list_resp)}
            self.assertNotIn(
                private_id,
                ids,
                f"{username} should not see another user's private shelf in list",
            )
            self.assertIn(
                listed_id, ids, f"{username} should see another user's listed shelf"
            )

            detail = assert_response(self.client.get(f"/api/v1/shelves/{private_id}/"))
            self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_shelf_visibility(self):
        # Owner can create a group shelf.
        self.client.login(username="owner", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(create)["id"]
        create_payload = response_data_dict(create)
        self.assertIsNone(create_payload["owner_user"])
        self._assert_compact_user_payload(
            payload_dict(create_payload, "created_by"), user=self.owner
        )

        # Member can see it in list.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        list_resp = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_list(list_resp)
        self.assertIn(shelf_id, {r["id"] for r in results})
        group_row = next(row for row in results if row["id"] == shelf_id)
        self.assertIsNone(group_row["owner_user"])
        self._assert_compact_user_payload(
            payload_dict(group_row, "created_by"), user=self.owner
        )
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        detail_payload = response_data_dict(detail)
        self.assertIsNone(detail_payload["owner_user"])
        self._assert_compact_user_payload(
            payload_dict(detail_payload, "created_by"), user=self.owner
        )

        # Non-member cannot retrieve it (404).
        self.client.logout()
        self.client.login(username="other", password="pw")
        list_for_non_member = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_for_non_member.status_code, status.HTTP_200_OK)
        non_member_ids = {row["id"] for row in response_data_list(list_for_non_member)}
        self.assertNotIn(shelf_id, non_member_ids)
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
