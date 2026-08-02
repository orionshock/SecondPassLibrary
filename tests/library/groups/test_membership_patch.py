from __future__ import annotations

import json

from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
)


class LibraryGroupMembershipPatchTests(LibraryGroupMembershipApiTestCase):
    def test_patch_updates_is_curator(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(),
            json.dumps({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["user"]["profile_id"], str(self.target.profile.id)
        )
        self.assertEqual(
            set(response.json()["user"]), {"profile_id", "username"}
        )
        self.assertNotIn("id", response.json())
        self.assertTrue(response.json()["is_curator"])

        demote = self.client.patch(
            self.membership_detail_url(),
            json.dumps({"is_curator": False}),
            content_type="application/json",
        )
        self.assertEqual(demote.status_code, 200)
        self.assertEqual(set(demote.json()["user"]), {"profile_id", "username"})
        self.assertFalse(demote.json()["is_curator"])

    def test_patch_rejects_role_and_does_not_change_global_role(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        url = self.membership_detail_url()
        original_role = self.target.profile.role

        response = self.client.patch(
            url,
            json.dumps({"role": "librarian", "is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json())
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.role, original_role)
        self.assertFalse(
            self.target.library_group_memberships.get(group=self.club).is_curator
        )

    def test_patch_rejects_unknown_field(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(),
            json.dumps({"unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown", response.json())

    def test_patch_missing_membership_returns_404(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(user=self.other),
            json.dumps({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
