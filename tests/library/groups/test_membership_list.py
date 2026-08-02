from __future__ import annotations

import json

from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
)


class LibraryGroupMembershipListTests(LibraryGroupMembershipApiTestCase):
    def test_group_members_and_librarian_manager_owner_can_list_memberships(self):
        expected_user_ids = {str(self.reader.profile.id), str(self.target.profile.id)}

        for username in ["reader", "target", "librarian", "manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.get(self.membership_list_url())

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["count"], 2)
                self.assertIsNone(payload["next"])
                self.assertIsNone(payload["previous"])
                self.assertEqual(
                    {row["user"]["profile_id"] for row in payload["results"]},
                    expected_user_ids,
                )
                self.assertEqual(
                    set(payload["results"][0]["user"]),
                    {"profile_id", "username"},
                )
                self.assertNotIn("id", payload["results"][0])

    def test_nonmember_reader_cannot_list_memberships(self):
        self.assertTrue(self.client.login(username="other", password="pw"))

        response = self.client.get(self.membership_list_url())

        self.assertEqual(response.status_code, 404)

    def test_reader_and_librarian_cannot_mutate_memberships(self):
        for username in ["reader", "librarian"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))
                post_response = self.client.post(
                    self.membership_list_url(),
                    json.dumps({"user_id": str(self.other.profile.id)}),
                    content_type="application/json",
                )
                patch_response = self.client.patch(
                    self.membership_detail_url(),
                    json.dumps({"is_curator": True}),
                    content_type="application/json",
                )
                delete_response = self.client.delete(self.membership_detail_url())

                self.assertEqual(post_response.status_code, 403)
                self.assertEqual(patch_response.status_code, 403)
                self.assertEqual(delete_response.status_code, 403)

    def test_owner_can_add_update_and_remove_memberships(self):
        self.assertTrue(self.client.login(username="owner", password="pw"))

        created = self.client.post(
            self.membership_list_url(),
            json.dumps({"user_id": str(self.other.profile.id)}),
            content_type="application/json",
        )
        updated = self.client.patch(
            self.membership_detail_url(user=self.other),
            json.dumps({"is_curator": True}),
            content_type="application/json",
        )
        deleted = self.client.delete(self.membership_detail_url(user=self.other))

        self.assertEqual(created.status_code, 201)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(deleted.status_code, 204)

    def test_post_rejects_role_without_creating_membership_or_changing_global_role(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        original_role = self.other.profile.role

        response = self.client.post(
            self.membership_list_url(),
            json.dumps(
                {
                    "user_id": str(self.other.profile.id),
                    "is_curator": True,
                    "role": "librarian",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.role, original_role)
        self.assertFalse(
            self.other.library_group_memberships.filter(group=self.club).exists()
        )

    def test_hidden_group_returns_404_before_payload_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.membership_list_url(self.hidden),
            json.dumps({"user_id": "not-a-uuid", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_get_list_does_not_expose_unrelated_group_memberships(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(self.membership_list_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            str(self.other.profile.id),
            {
                row["user"]["profile_id"]
                for row in response.json()["results"]
            },
        )
