from __future__ import annotations

from shelves.models import Shelf, ShelfItem
from tests.shelves.bearer.helpers import ShelvesBearerApiTestCase
from tests.utils.responses import (
    assert_response,
    payload_dict,
    payload_list,
    response_data_dict,
)


class ShelvesBearerVisibilityTests(ShelvesBearerApiTestCase):
    def test_bearer_can_read_listed_other_users_shelf_but_not_edit(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Listed", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        shelf_id = str(response_data_dict(created)["id"])
        ShelfItem.objects.create(
            shelf_id=shelf_id,
            book=self.book_in_group,
            position=0,
            added_by=self.other,
        )
        self.client.logout()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        results = payload_list(list_data, "results")
        ids = {str(r["id"]) for r in results}
        self.assertIn(shelf_id, ids)
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])
        self.assertEqual(
            set(payload_dict(row, "owner_user")), {"profile_id", "username"}
        )
        self.assertEqual(
            set(payload_dict(row, "created_by")), {"profile_id", "username"}
        )

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 200)
        detail_data = response_data_dict(detail)
        self.assertFalse(detail_data["can_edit"])
        self.assertEqual(
            set(payload_dict(detail_data, "owner_user")),
            {"profile_id", "username"},
        )
        self.assertEqual(
            set(payload_dict(detail_data, "created_by")),
            {"profile_id", "username"},
        )

    def test_bearer_scope_filters_preserve_visibility_and_edit_contracts(self):
        personal_shelf_id = self._create_personal_shelf_as_owner()

        self.client.logout()
        self.client.login(username="o", password="pw")
        listed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Other Listed",
                    "owner_type": "user",
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        listed_shelf_id = str(response_data_dict(listed)["id"])
        ShelfItem.objects.create(
            shelf_id=listed_shelf_id,
            book=self.book_in_group,
            position=0,
            added_by=self.other,
        )
        private = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Other Private", "owner_type": "user"},
                format="json",
            ),
        )
        private_shelf_id = str(response_data_dict(private)["id"])
        self.client.logout()
        group_shelf_id, _item_id = self._create_group_shelf_with_item_as_session_user()

        personal_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=personal",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        personal_rows = payload_list(response_data_dict(personal_response), "results")
        self.assertEqual(
            {str(row["id"]) for row in personal_rows},
            {personal_shelf_id},
        )
        self.assertTrue(personal_rows[0]["can_edit"])

        shared_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=shared",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        shared_rows = payload_list(response_data_dict(shared_response), "results")
        shared_by_id = {str(row["id"]): row for row in shared_rows}
        self.assertIn(listed_shelf_id, shared_by_id)
        self.assertIn(group_shelf_id, shared_by_id)
        self.assertNotIn(private_shelf_id, shared_by_id)
        self.assertFalse(shared_by_id[listed_shelf_id]["can_edit"])
        self.assertFalse(shared_by_id[group_shelf_id]["can_edit"])

    def test_bearer_hides_empty_other_listed_shelf_but_keeps_empty_owned_and_group_shelves(self):
        personal_shelf_id = self._create_personal_shelf_as_owner()
        empty_listed = Shelf.objects.create(
            name="Empty Other Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.other,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.other,
        )
        hidden_only = Shelf.objects.create(
            name="Hidden Only Other Listed",
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
        group_shelf = Shelf.objects.create(
            name="Empty Group Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.user,
        )

        personal_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=personal&include_preview_books=true",
                HTTP_AUTHORIZATION=self._auth,
            )
        )
        personal_by_id = {
            str(row["id"]): row
            for row in payload_list(response_data_dict(personal_response), "results")
        }
        self.assertEqual(personal_by_id[personal_shelf_id]["item_count"], 0)
        self.assertEqual(personal_by_id[personal_shelf_id]["preview_books"], [])

        shared_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=shared&include_preview_books=true",
                HTTP_AUTHORIZATION=self._auth,
            )
        )
        shared_by_id = {
            str(row["id"]): row
            for row in payload_list(response_data_dict(shared_response), "results")
        }
        self.assertNotIn(str(empty_listed.id), shared_by_id)
        self.assertNotIn(str(hidden_only.id), shared_by_id)
        self.assertEqual(shared_by_id[str(group_shelf.id)]["item_count"], 0)
        self.assertEqual(shared_by_id[str(group_shelf.id)]["preview_books"], [])

    def test_bearer_cannot_read_private_other_users_shelf(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Private", "owner_type": "user", "visibility": "private"},
                format="json",
            )
        )
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        ids = {str(r["id"]) for r in payload_list(list_data, "results")}
        self.assertNotIn(shelf_id, ids)

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 404)

    def test_bearer_can_read_visible_group_shelf_but_not_edit(self):
        shelf_id, _item_id = self._create_group_shelf_with_item_as_session_user()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        results = payload_list(list_data, "results")
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])
        self.assertIsNone(row["owner_user"])
        self.assertEqual(
            set(payload_dict(row, "created_by")), {"profile_id", "username"}
        )

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 200)
        detail_data = response_data_dict(detail)
        self.assertFalse(detail_data["can_edit"])
        self.assertIsNone(detail_data["owner_user"])
        self.assertEqual(
            set(payload_dict(detail_data, "created_by")),
            {"profile_id", "username"},
        )

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 403)

        put = assert_response(
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope2"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 403)

        delete = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(delete.status_code, 403)
