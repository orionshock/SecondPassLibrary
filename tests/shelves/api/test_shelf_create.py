from __future__ import annotations

import pytest
from rest_framework import status

from core import server_settings
from shelves.models import ShelfItem
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import assert_response, payload_dict, response_data_dict


pytestmark = [pytest.mark.integration]


class ShelfCreateEndpointTests(BaseShelvesAPITest):
    def test_advanced_group_lists_support_shelf_create_role_scoping(self):
        server_settings.enable_advanced_library_groups()

        for username in ["librarian", "manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = assert_response(self.client.get("/api/v1/library/groups/"))
                rows = response_data_dict(response)["results"]
                self.assertEqual(
                    {row["name"] for row in rows},
                    {"Common Room", "G", "Hidden"},
                )
                self.assertTrue(all("capabilities" not in row for row in rows))

        self.client.logout()
        self.client.login(username="curator", password="pw")
        curator_rows = response_data_dict(
            assert_response(self.client.get("/api/v1/library/groups/"))
        )["results"]
        self.assertEqual(
            {row["name"] for row in curator_rows}, {"Common Room", "G"}
        )
        self.assertTrue(all("capabilities" not in row for row in curator_rows))

        self.client.logout()
        self.client.login(username="reader", password="pw")
        reader_rows = response_data_dict(
            assert_response(self.client.get("/api/v1/library/groups/"))
        )["results"]
        self.assertEqual({row["name"] for row in reader_rows}, {"Common Room", "G"})
        self.assertTrue(all("capabilities" not in row for row in reader_rows))

    def test_advanced_group_shelf_create_for_broad_role_and_curator(self):
        server_settings.enable_advanced_library_groups()

        for username in ["librarian", "manager", "owner", "curator"]:
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = assert_response(
                    self.client.post(
                        "/api/v1/shelves/",
                        data={
                            "name": f"{username} group shelf",
                            "owner_type": "group",
                            "owner_group": str(self.group.id),
                            "visibility": "private",
                        },
                        format="json",
                    )
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                payload = response_data_dict(response)
                self.assertEqual(payload["owner_type"], "group")
                self.assertEqual(
                    payload_dict(payload, "owner_group")["id"], self.group.id
                )
                self.assertEqual(payload["visibility"], "private")

    def test_public_group_shelf_create_authorization_when_advanced_groups_disabled(self):
        server_settings.set_advanced_library_groups_enabled(False)

        self.client.login(username="librarian", password="pw")
        allowed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Common Room Picks",
                    "description": "Shared presentation shelf.",
                    "owner_type": "group",
                    "owner_group": str(self.public.id),
                    "visibility": "private",
                },
                format="json",
            )
        )

        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(allowed)
        self.assertEqual(payload["owner_type"], "group")
        self.assertEqual(payload_dict(payload, "owner_group")["id"], self.public.id)
        self.assertEqual(payload["visibility"], "private")
        self.assertEqual(payload["item_count"], 0)

        shelf_id = payload["id"]
        updated = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Updated in simple mode."},
                format="json",
            )
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
            )
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        removed = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{response_data_dict(added)['id']}/"
            )
        )
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        deleted = assert_response(self.client.delete(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        denied = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Reader Public Shelf",
                    "owner_type": "group",
                    "owner_group": str(self.public.id),
                    "visibility": "private",
                },
                format="json",
            )
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_custom_group_shelf_workflow_remains_active_in_simple_mode(self):
        server_settings.set_advanced_library_groups_enabled(False)
        self.client.login(username="curator", password="pw")

        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Existing Group Workflow",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                    "visibility": "private",
                },
                format="json",
            )
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]

        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/")).status_code,
            status.HTTP_200_OK,
        )
        updated = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Still editable in Simple Mode."},
                format="json",
            )
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)

    def test_create_personal_shelf_when_advanced_groups_disabled(self):
        server_settings.set_advanced_library_groups_enabled(False)
        self.client.login(username="reader", password="pw")

        response = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Browser Shelf",
                    "description": "Created from the Product UI.",
                    "owner_type": "user",
                    "visibility": "private",
                },
                format="json",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(response)
        self.assertEqual(payload["name"], "Browser Shelf")
        self.assertEqual(payload["owner_type"], "user")
        self.assertEqual(payload["visibility"], "private")
        self.assertIsNone(payload["owner_group"])
        self.assertEqual(payload["item_count"], 0)
        detail_payload = response_data_dict(
            assert_response(self.client.get(f"/api/v1/shelves/{payload['id']}/"))
        )
        self.assertEqual(set(payload), set(detail_payload))
        self._assert_compact_user_payload(
            payload_dict(payload, "owner_user"), user=self.reader
        )

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

        owner_results = response_data_dict(
            assert_response(self.client.get("/api/v1/shelves/"))
        )["results"]
        owner_ids = {row["id"] for row in owner_results}
        self.assertIn(private_id, owner_ids)
        self.assertIn(listed_id, owner_ids)

        self.client.logout()
        self.client.login(username="other", password="pw")
        empty_listed_resp = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(empty_listed_resp.status_code, status.HTTP_200_OK)
        empty_ids = {
            row["id"]
            for row in response_data_dict(empty_listed_resp)["results"]
        }
        self.assertNotIn(listed_id, empty_ids)
        self.assertNotIn(private_id, empty_ids)

        ShelfItem.objects.create(
            shelf_id=listed_id,
            book=self.book_public,
            added_by=self.reader,
        )
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
