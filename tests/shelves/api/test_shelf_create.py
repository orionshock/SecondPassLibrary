from __future__ import annotations

import pytest
from rest_framework import status

from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import assert_response, payload_dict, response_data_dict


pytestmark = [pytest.mark.integration]


class ShelfCreateEndpointTests(BaseShelvesAPITest):
    def test_create_user_shelf_and_list_visibility_private_vs_listed(self):
        self.client.login(username="reader", password="pw")
        r1 = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Private", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        private_payload = response_data_dict(r1)
        private_id = private_payload["id"]
        private_owner = payload_dict(private_payload, "owner_user")
        private_creator = payload_dict(private_payload, "created_by")
        self._assert_compact_user_payload(private_owner, user=self.reader)
        self._assert_compact_user_payload(private_creator, user=self.reader)
        private_detail = assert_response(
            self.client.get(f"/api/v1/shelves/{private_id}/")
        )
        self.assertEqual(private_detail.status_code, status.HTTP_200_OK)
        private_detail_payload = response_data_dict(private_detail)
        self._assert_compact_user_payload(
            payload_dict(private_detail_payload, "owner_user"), user=self.reader
        )
        self._assert_compact_user_payload(
            payload_dict(private_detail_payload, "created_by"), user=self.reader
        )

        r2 = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Listed", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        listed_id = response_data_dict(r2)["id"]

        self.client.logout()
        self.client.login(username="other", password="pw")
        list_resp = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_dict(list_resp)["results"]
        ids = {row["id"] for row in results}
        self.assertIn(listed_id, ids)
        self.assertNotIn(private_id, ids)
        listed_row = next(row for row in results if row["id"] == listed_id)
        owner_user = payload_dict(listed_row, "owner_user")
        created_by = payload_dict(listed_row, "created_by")
        self._assert_compact_user_payload(owner_user, user=self.reader)
        self._assert_compact_user_payload(created_by, user=self.reader)
