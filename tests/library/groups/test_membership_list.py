from __future__ import annotations

from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
    json_body,
)


class LibraryReWrite2607GroupMembershipListTests(LibraryGroupMembershipApiTestCase):
    def test_manager_and_owner_can_list_group_memberships(self):
        expected_user_ids = {str(self.reader.profile.id), str(self.target.profile.id)}

        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.get(self.membership_list_url())

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual({row["user_id"] for row in payload}, expected_user_ids)
                self.assertEqual({row["group_id"] for row in payload}, {str(self.club.id)})

    def test_unauthorized_users_cannot_list_or_manage_memberships(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        list_response = self.client.get(self.membership_list_url())
        post_response = self.client.post(
            self.membership_list_url(),
            json_body({"user_id": str(self.other.profile.id)}),
            content_type="application/json",
        )
        patch_response = self.client.patch(
            self.membership_detail_url(),
            json_body({"is_curator": True}),
            content_type="application/json",
        )
        delete_response = self.client.delete(self.membership_detail_url())

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_hidden_group_returns_404_before_payload_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.membership_list_url(self.hidden),
            json_body({"user_id": "not-a-uuid", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_get_list_does_not_expose_unrelated_group_memberships(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(self.membership_list_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.other.profile.id), {row["user_id"] for row in response.json()})
