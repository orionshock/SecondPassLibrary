from __future__ import annotations

from accounts.models import UserProfile
from library.models import LibraryGroupMembership
from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
    json_body,
)


class LibraryGroupMembershipCreateTests(LibraryGroupMembershipApiTestCase):
    def test_post_requires_user_id_uuid(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        missing = self.client.post(
            self.membership_list_url(),
            json_body({}),
            content_type="application/json",
        )
        invalid = self.client.post(
            self.membership_list_url(),
            json_body({"user_id": "not-a-uuid"}),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("user_id", missing.json())
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("user_id", invalid.json())

    def test_post_creates_membership_and_returns_uuid_payload(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            self.membership_list_url(),
            json_body(
                {
                    "user_id": str(self.other.profile.id),
                    "role": UserProfile.ROLE_LIBRARIAN,
                    "is_curator": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["user"]["profile_id"], str(self.other.profile.id))
        self.assertEqual(payload["user"]["username"], self.other.get_username())
        self.assertNotIn("email", payload["user"])
        self.assertNotIn("id", payload)
        self.assertTrue(payload["is_curator"])
        self.assertIn("created_at", payload)
        self.assertIn("updated_at", payload)
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.role, UserProfile.ROLE_LIBRARIAN)

    def test_post_is_idempotent_and_returns_existing_membership(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        body = json_body({"user_id": str(self.target.profile.id), "is_curator": True})

        first = self.client.post(self.membership_list_url(), body, content_type="application/json")
        second = self.client.post(self.membership_list_url(), body, content_type="application/json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            first.json()["user"]["profile_id"], second.json()["user"]["profile_id"]
        )
        self.assertEqual(
            LibraryGroupMembership.objects.filter(
                user=self.target, group=self.club
            ).count(),
            1,
        )
        self.assertEqual(
            LibraryGroupMembership.objects.filter(user=self.target, group=self.club).count(),
            1,
        )
