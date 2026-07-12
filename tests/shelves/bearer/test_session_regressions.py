from __future__ import annotations

from tests.shelves.bearer.helpers import ShelvesBearerApiTestCase
from tests.utils.responses import assert_response, response_data_dict


class ShelvesSessionAuthRegressionTests(ShelvesBearerApiTestCase):
    def test_session_auth_curator_can_edit_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        self.client.force_login(self.user)
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(response_data_dict(detail)["can_edit"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Session allowed"},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, 200)

        move = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
            ),
        )
        self.assertEqual(move.status_code, 200)
