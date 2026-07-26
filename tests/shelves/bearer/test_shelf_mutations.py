from __future__ import annotations

from tests.shelves.bearer.helpers import ShelvesBearerApiTestCase
from tests.utils.responses import assert_response, response_data_dict


class ShelvesBearerShelfMutationTests(ShelvesBearerApiTestCase):
    def test_bearer_can_patch_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "P2", "description": "d"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 200)
        data = response_data_dict(resp)
        self.assertEqual(data["name"], "P2")
        self.assertTrue(data["can_edit"])

    def test_bearer_put_is_not_supported_for_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        # Set initial description via PATCH first.
        patch1 = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Before", "visibility": "listed"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch1.status_code, 200)

        put = assert_response(
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "After"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 405)

        data = response_data_dict(
            assert_response(
                self.client.get(
                    f"/api/v1/shelves/{shelf_id}/",
                    HTTP_AUTHORIZATION=self._auth,
                )
            )
        )
        self.assertNotEqual(data["name"], "After")
        self.assertEqual(data["description"], "Before")
        self.assertEqual(data["visibility"], "listed")

    def test_bearer_cannot_patch_other_users_shelf(self):
        # Create a listed shelf for other using session auth (baseline behavior).
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "O", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        resp = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Hacked"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def test_bearer_cannot_delete_other_users_shelf(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "O", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        resp = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def test_bearer_can_delete_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 204)
