from __future__ import annotations

import pytest
from rest_framework import status

from shelves.models import Shelf, ShelfItem
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import (
    assert_response,
    payload_dict,
    response_data_dict,
    response_data_list,
)


pytestmark = [pytest.mark.integration]


class ShelfListEndpointTests(BaseShelvesAPITest):
    def test_list_scopes_partition_visible_shelves_and_preserve_empty_rows(self):
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
        ShelfItem.objects.create(
            shelf=other_listed,
            book=self.book_public,
            position=0,
            added_by=self.other,
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
        all_response = assert_response(self.client.get("/api/v1/shelves/?scope=all"))
        self.assertEqual(all_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(default_response), response_data_dict(all_response))

        personal_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal"),
        )
        self.assertEqual(personal_response.status_code, status.HTTP_200_OK)
        personal_ids = {row["id"] for row in response_data_list(personal_response)}
        self.assertEqual(personal_ids, {str(own_private.id), str(own_listed.id)})
        personal_page = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal&page_size=1")
        )
        self.assertEqual(response_data_dict(personal_page)["count"], 2)
        self.assertIn("scope=personal", response_data_dict(personal_page)["next"])

        shared_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=shared"),
        )
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        shared_rows = response_data_list(shared_response)
        shared_ids = {row["id"] for row in shared_rows}
        self.assertEqual(shared_ids, {str(other_listed.id)})
        self.assertNotIn(str(other_private.id), shared_ids)
        other_listed_row = next(
            row for row in shared_rows if row["id"] == str(other_listed.id)
        )
        self._assert_compact_user_payload(
            payload_dict(other_listed_row, "owner_user"),
            user=self.other,
        )
        self.assertEqual(other_listed_row["item_count"], 1)

        group_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=group")
        )
        self.assertEqual(group_response.status_code, status.HTTP_200_OK)
        group_rows = response_data_list(group_response)
        self.assertEqual({row["id"] for row in group_rows}, {str(group_shelf.id)})
        group_shelf_row = group_rows[0]
        self.assertEqual(payload_dict(group_shelf_row, "owner_group")["name"], "G")
        self.assertEqual(group_shelf_row["item_count"], 0)

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

    def test_list_hides_empty_or_hidden_only_listed_shelves_owned_by_others(self):
        empty = Shelf.objects.create(
            name="Empty Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.other,
        )
        hidden_only = Shelf.objects.create(
            name="Hidden Only Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.other,
        )
        ShelfItem.objects.create(
            shelf=hidden_only,
            book=self.book_hidden,
            position=0,
            added_by=self.other,
        )

        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get("/api/v1/shelves/?scope=shared&include_preview_books=true")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response_data_list(response)
        ids = {row["id"] for row in rows}
        self.assertNotIn(str(empty.id), ids)
        self.assertNotIn(str(hidden_only.id), ids)

        self.client.logout()
        self.client.login(username="other", password="pw")
        owner_response = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal&include_preview_books=true")
        )
        owner_rows = {
            row["id"]: row for row in response_data_list(owner_response)
        }
        self.assertEqual(owner_rows[str(empty.id)]["item_count"], 0)
        self.assertEqual(owner_rows[str(empty.id)]["preview_books"], [])
        self.assertEqual(owner_rows[str(hidden_only.id)]["item_count"], 0)
        self.assertEqual(owner_rows[str(hidden_only.id)]["preview_books"], [])

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
                f"/api/v1/shelves/?scope=group&owner_group={self.group.id}"
            ),
        )
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        shared_results = response_data_list(shared_response)
        self.assertIn(shelf_id, {row["id"] for row in shared_results})

    def test_list_ordering_name_and_item_count_with_scopes(self):
        own_z = Shelf.objects.create(
            name="Zulu",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )
        own_a = Shelf.objects.create(
            name="Alpha",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )
        shared = Shelf.objects.create(
            name="Bravo",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.other,
        )
        ShelfItem.objects.create(
            shelf=own_z,
            book=self.book_public,
            position=0,
            added_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=own_z,
            book=self.book_in_group,
            position=1,
            added_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=own_a,
            book=self.book_public,
            position=0,
            added_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shared,
            book=self.book_public,
            position=0,
            added_by=self.other,
        )

        self.client.login(username="reader", password="pw")
        personal_name = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal&ordering=name")
        )
        self.assertEqual(personal_name.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["name"] for row in response_data_list(personal_name)],
            ["Alpha", "Zulu"],
        )

        personal_count = assert_response(
            self.client.get("/api/v1/shelves/?scope=personal&ordering=-item_count")
        )
        self.assertEqual(personal_count.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [
                (row["name"], row["item_count"])
                for row in response_data_list(personal_count)
            ],
            [("Zulu", 2), ("Alpha", 1)],
        )

        shared_name = assert_response(
            self.client.get("/api/v1/shelves/?scope=shared&ordering=name")
        )
        self.assertEqual(shared_name.status_code, status.HTTP_200_OK)
        self.assertIn("Bravo", [row["name"] for row in response_data_list(shared_name)])

    def test_list_ordering_owner_group_and_preview_books_compose(self):
        self.client.login(username="owner", password="pw")
        zulu = Shelf.objects.create(
            name="Zulu Group Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        alpha = Shelf.objects.create(
            name="Alpha Group Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        ShelfItem.objects.create(
            shelf=zulu,
            book=self.book_in_group,
            position=0,
            added_by=self.owner,
        )
        ShelfItem.objects.create(
            shelf=alpha,
            book=self.book_in_group,
            position=0,
            added_by=self.owner,
        )

        response = assert_response(
            self.client.get(
                f"/api/v1/shelves/?scope=group&owner_group={self.group.id}&ordering=name&include_preview_books=true"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response_data_list(response)
        self.assertEqual(
            [row["name"] for row in rows],
            ["Alpha Group Shelf", "Zulu Group Shelf"],
        )
        self.assertIn("preview_books", rows[0])
        self.assertEqual(rows[0]["preview_books"][0]["title"], "B1")

    def test_list_ordering_invalid_returns_400(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get("/api/v1/shelves/?ordering=created_at"),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(response))

    def test_list_filters_reject_invalid_scope_and_malformed_uuids(self):
        self.client.login(username="reader", password="pw")

        invalid_scope = assert_response(
            self.client.get("/api/v1/shelves/?scope=unknown"),
        )
        self.assertEqual(invalid_scope.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scope", response_data_dict(invalid_scope))
        self.assertEqual(
            response_data_dict(invalid_scope)["scope"],
            "Must be one of: all, personal, shared, group.",
        )

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
