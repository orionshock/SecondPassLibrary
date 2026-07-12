from __future__ import annotations

from accounts.models import UserProfile
from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
    json_body,
)


class LibraryGroupMembershipPatchTests(LibraryGroupMembershipApiTestCase):
    def test_patch_updates_role_and_is_curator(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(),
            json_body({"role": UserProfile.ROLE_LIBRARIAN, "is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], UserProfile.ROLE_LIBRARIAN)
        self.assertTrue(response.json()["is_curator"])
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.role, UserProfile.ROLE_LIBRARIAN)

        demote = self.client.patch(
            self.membership_detail_url(),
            json_body({"is_curator": False}),
            content_type="application/json",
        )
        self.assertEqual(demote.status_code, 200)
        self.assertFalse(demote.json()["is_curator"])

    def test_patch_rejects_unknown_and_invalid_role(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        url = self.membership_detail_url()

        unknown = self.client.patch(
            url,
            json_body({"unknown": "field"}),
            content_type="application/json",
        )
        invalid_role = self.client.patch(
            url,
            json_body({"role": ""}),
            content_type="application/json",
        )

        self.assertEqual(unknown.status_code, 400)
        self.assertIn("unknown", unknown.json())
        self.assertEqual(invalid_role.status_code, 400)
        self.assertIn("role", invalid_role.json())

    def test_patch_missing_membership_returns_404(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(user=self.other),
            json_body({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
