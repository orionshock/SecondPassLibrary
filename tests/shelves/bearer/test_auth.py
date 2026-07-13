from __future__ import annotations

from accounts.services import get_or_create_profile
from tests.shelves.bearer.helpers import ShelvesBearerApiTestCase
from tests.utils.responses import assert_response, payload_dict, response_data_dict


class ShelvesBearerAuthTests(ShelvesBearerApiTestCase):
    def test_bearer_can_create_personal_shelf(self):
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Mine", "owner_type": "user", "visibility": "private"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = response_data_dict(resp)
        self.assertEqual(data["owner_type"], "user")
        owner_user = payload_dict(data, "owner_user")
        profile = get_or_create_profile(user=self.user)
        self.assertEqual(set(owner_user), {"profile_id", "username"})
        self.assertEqual(owner_user["profile_id"], profile.id)
        created_by = payload_dict(data, "created_by")
        self.assertEqual(set(created_by), {"profile_id", "username"})
        self.assertEqual(created_by["profile_id"], profile.id)
        self.assertTrue(data["can_edit"])

    def test_bearer_cannot_create_group_shelf(self):
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)
