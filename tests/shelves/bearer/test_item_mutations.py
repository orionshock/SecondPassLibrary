from __future__ import annotations

from tests.shelves.bearer.helpers import ShelvesBearerApiTestCase
from tests.utils.responses import assert_response, response_data_dict


class ShelvesBearerItemMutationTests(ShelvesBearerApiTestCase):
    def test_bearer_cannot_manage_items_on_visible_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 403)

        move = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(move.status_code, 403)

        remove = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(remove.status_code, 403)

    def test_bearer_can_add_and_remove_accessible_book_on_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()

        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 201)
        item_id = str(response_data_dict(add)["id"])

        items = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/items/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(items.status_code, 200)

        rm = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(rm.status_code, 204)

    def test_bearer_cannot_add_inaccessible_book_to_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_hidden.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 403)

    def test_bearer_can_reorder_items_in_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        add1 = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add1.status_code, 201)
        item_id = str(response_data_dict(add1)["id"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 5},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(response_data_dict(patch)["position"], 0)
