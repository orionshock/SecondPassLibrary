from __future__ import annotations

import pytest
from rest_framework import status

from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import (
    assert_response,
    payload_dict,
    payload_list,
    response_data_dict,
    response_data_list,
)

from shelves.models import Shelf


pytestmark = [pytest.mark.integration]


class ShelvesListTests(BaseShelvesAPITest):
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
        payload = response_data_dict(list_resp)
        results = payload_list(payload, "results")
        ids = {row["id"] for row in results}
        self.assertIn(listed_id, ids)
        self.assertNotIn(private_id, ids)
        listed_row = next(row for row in results if row["id"] == listed_id)
        owner_user = payload_dict(listed_row, "owner_user")
        created_by = payload_dict(listed_row, "created_by")
        self._assert_compact_user_payload(owner_user, user=self.reader)
        self._assert_compact_user_payload(created_by, user=self.reader)

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

    def test_list_scope_personal_and_shared_preserve_visibility_rules(self):
        own_private = Shelf.objects.create(
            name="Own Private",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )
        own_listed = Shelf.objects.create(
            name="Own Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.reader,
        )
        other_private = Shelf.objects.create(
            name="Other Private",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.other,
        )
        other_listed = Shelf.objects.create(
            name="Other Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.other,
        )
        group_shelf = Shelf.objects.create(
            name="Group Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )

        self.client.login(username="reader", password="pw")

        default_response = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        default_ids = {row["id"] for row in response_data_list(default_response)}
        self.assertEqual(
            default_ids,
            {
                str(own_private.id),
                str(own_listed.id),
                str(other_listed.id),
                str(group_shelf.id),
            },
        )

        personal_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal"),
        )
        self.assertEqual(personal_response.status_code, status.HTTP_200_OK)
        personal_ids = {row["id"] for row in response_data_list(personal_response)}
        self.assertEqual(personal_ids, {str(own_private.id), str(own_listed.id)})

        shared_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=shared"),
        )
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        shared_rows = response_data_list(shared_response)
        shared_ids = {row["id"] for row in shared_rows}
        self.assertEqual(shared_ids, {str(other_listed.id), str(group_shelf.id)})
        self.assertNotIn(str(other_private.id), shared_ids)
        other_listed_row = next(
            row for row in shared_rows if row["id"] == str(other_listed.id)
        )
        group_shelf_row = next(
            row for row in shared_rows if row["id"] == str(group_shelf.id)
        )
        self._assert_compact_user_payload(
            payload_dict(other_listed_row, "owner_user"),
            user=self.other,
        )
        self.assertEqual(
            payload_dict(group_shelf_row, "owner_group")["name"],
            "G",
        )

        for username in ("manager", "owner"):
            self.client.logout()
            self.client.login(username=username, password="pw")
            for scope in ("personal", "shared"):
                response = assert_response(
                    self.client.get(f"/api/v1/shelves/?scope={scope}"),
                )
                ids = {row["id"] for row in response_data_list(response)}
                self.assertNotIn(
                    str(other_private.id),
                    ids,
                    f"{username} should not see another user's private shelf in {scope} scope",
                )

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

    def test_list_filter_owner_group(self):
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

        list_resp = assert_response(
            self.client.get(f"/api/v1/shelves/?owner_group={self.group.id}")
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = response_data_list(list_resp)
        self.assertIn(shelf_id, {r["id"] for r in results})

        shared_response = assert_response(
            self.client.get(
                f"/api/v1/shelves/?scope=shared&owner_group={self.group.id}"
            ),
        )
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        shared_results = response_data_list(shared_response)
        self.assertIn(shelf_id, {row["id"] for row in shared_results})

    def test_list_filters_reject_invalid_scope_and_malformed_uuids(self):
        self.client.login(username="reader", password="pw")

        invalid_scope = assert_response(
            self.client.get("/api/v1/shelves/?scope=unknown"),
        )
        self.assertEqual(invalid_scope.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scope", response_data_dict(invalid_scope))

        malformed_owner_group = assert_response(
            self.client.get("/api/v1/shelves/?owner_group=not-a-uuid"),
        )
        self.assertEqual(
            malformed_owner_group.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            "owner_group",
            response_data_dict(malformed_owner_group),
        )

        malformed_book = assert_response(
            self.client.get("/api/v1/shelves/?book=not-a-uuid"),
        )
        self.assertEqual(malformed_book.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book", response_data_dict(malformed_book))

    def test_list_filter_rejects_personal_scope_with_owner_group(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(
                f"/api/v1/shelves/?scope=personal&owner_group={self.group.id}"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_group", response_data_dict(response))

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
