from __future__ import annotations

import json

from library.models import LibraryGroupMembership
from library.roles import is_curator
from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
)


class LibraryPublicMembershipApiTests(LibraryGroupMembershipApiTestCase):
    def test_patch_rejects_public_curator_membership(self):
        LibraryGroupMembership.objects.create(user=self.target, group=self.public)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(group=self.public),
            json.dumps({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("is_curator", response.json())
        membership = LibraryGroupMembership.objects.get(
            user=self.target, group=self.public
        )
        self.assertFalse(membership.is_curator)
        self.assertFalse(is_curator(self.target, self.public))

    def test_post_rejects_public_curator_membership_without_persisting_it(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            self.membership_list_url(group=self.public),
            json.dumps(
                {"user_id": str(self.other.profile.id), "is_curator": True}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("is_curator", response.json())
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                user=self.other, group=self.public
            ).exists()
        )

    def test_public_membership_accepts_false_or_omitted_curator(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        created = self.client.post(
            self.membership_list_url(group=self.public),
            json.dumps({"user_id": str(self.other.profile.id)}),
            content_type="application/json",
        )
        patched = self.client.patch(
            self.membership_detail_url(group=self.public, user=self.other),
            json.dumps({"is_curator": False}),
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(patched.status_code, 200)
        membership = LibraryGroupMembership.objects.get(
            user=self.other, group=self.public
        )
        self.assertFalse(membership.is_curator)

    def test_non_public_curator_create_and_update_still_work(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        created = self.client.post(
            self.membership_list_url(),
            json.dumps(
                {"user_id": str(self.other.profile.id), "is_curator": True}
            ),
            content_type="application/json",
        )
        updated = self.client.patch(
            self.membership_detail_url(user=self.other),
            json.dumps({"is_curator": False}),
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["is_curator"])
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["is_curator"])
