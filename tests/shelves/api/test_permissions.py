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


class ShelvesPermissionTests(BaseShelvesAPITest):
    def test_can_edit_user_shelf_owner_true_other_false(self):
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

        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["can_edit"], True)

        self.client.logout()
        self.client.login(username="other", password="pw")
        detail2 = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_404_NOT_FOUND)

        # Listed shelf should be visible but not editable to other users.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        created2 = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "L", "owner_type": "user", "visibility": "listed"},
                format="json",
            ),
        )
        self.assertEqual(created2.status_code, status.HTTP_201_CREATED)
        shelf2_id = response_data_dict(created2)["id"]

        self.client.logout()
        self.client.login(username="other", password="pw")
        detail3 = assert_response(self.client.get(f"/api/v1/shelves/{shelf2_id}/"))
        self.assertEqual(detail3.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail3)["can_edit"], False)

    def test_put_shelf_behaves_like_partial_update(self):
        self.client.login(username="reader", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Before",
                    "description": "Desc",
                    "owner_type": "user",
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]

        put = assert_response(
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "After"},
                format="json",
            ),
        )
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        payload = response_data_dict(put)
        self.assertEqual(payload["name"], "After")
        # PUT behaves like PATCH here: omitted fields are preserved.
        self.assertEqual(payload["description"], "Desc")
        self.assertEqual(payload["visibility"], "listed")

    def test_can_edit_group_shelf_curator_true_reader_false(self):
        self.client.login(username="owner", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]

        self.client.logout()
        self.client.login(username="curator", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["can_edit"], True)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        detail2 = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail2)["can_edit"], False)

    def test_can_edit_public_group_shelf_reader_false_librarian_true(self):
        self.client.login(username="owner", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "PGS",
                    "owner_type": "group",
                    "owner_group": str(self.public.id),
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = response_data_dict(created)["id"]

        self.client.logout()
        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        detail_payload = response_data_dict(detail)
        self.assertEqual(detail_payload["can_edit"], False)
        owner_group = payload_dict(detail_payload, "owner_group")
        self.assertEqual(owner_group["name"], self.public.name)
        self.assertTrue(owner_group["is_public_group"])

        self.client.logout()
        self.client.login(username="librarian", password="pw")
        detail2 = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail2)["can_edit"], True)

    def test_reader_cannot_create_group_shelf_for_reader_membership(self):
        self.client.login(username="reader", password="pw")
        resp = assert_response(
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
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_create_shelf_only_for_curated_non_public_group(self):
        self.client.login(username="curator", password="pw")

        allowed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Curated Shelf",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)

        unrelated = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Unrelated Shelf",
                    "owner_type": "group",
                    "owner_group": str(self.hidden_group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(unrelated.status_code, status.HTTP_403_FORBIDDEN)

        public = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Public Shelf",
                    "owner_type": "group",
                    "owner_group": str(self.public.id),
                },
                format="json",
            ),
        )
        self.assertEqual(public.status_code, status.HTTP_403_FORBIDDEN)

    def test_broad_roles_can_create_public_group_shelves(self):
        for username in ("librarian", "manager", "owner"):
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = assert_response(
                    self.client.post(
                        "/api/v1/shelves/",
                        data={
                            "name": f"{username} Public Shelf",
                            "owner_type": "group",
                            "owner_group": str(self.public.id),
                        },
                        format="json",
                    ),
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_group_shelf_with_listed_visibility_returns_400(self):
        self.client.login(username="owner", password="pw")
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_group_filter_does_not_leak_to_non_member(self):
        self.client.login(username="owner", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "HiddenShelf",
                    "owner_type": "group",
                    "owner_group": str(self.hidden_group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        list_resp = assert_response(
            self.client.get(f"/api/v1/shelves/?owner_group={self.hidden_group.id}")
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_list(list_resp)
        self.assertEqual(results, [])
