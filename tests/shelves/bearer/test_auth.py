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
        self.assertEqual(owner_user["profile_id"], profile.id)
        self.assertEqual(owner_user["first_name"], "Uma")
        self.assertEqual(owner_user["last_name"], "User")
        self.assertNotIn("id", owner_user)
        self.assertNotIn("email", owner_user)
        created_by = payload_dict(data, "created_by")
        self.assertEqual(created_by["profile_id"], profile.id)
        self.assertEqual(created_by["first_name"], "Uma")
        self.assertEqual(created_by["last_name"], "User")
        self.assertNotIn("id", created_by)
        self.assertNotIn("email", created_by)
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
