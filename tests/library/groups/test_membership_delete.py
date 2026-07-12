from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from library.models import LibraryGroup, LibraryGroupMembership
from tests.library.groups.membership_helpers import LibraryGroupMembershipApiTestCase
from tests.library.helpers import set_user_role


class LibraryGroupMembershipDeleteTests(LibraryGroupMembershipApiTestCase):
    def test_delete_removes_membership(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.membership_detail_url())

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            LibraryGroupMembership.objects.filter(user=self.target, group=self.club).exists()
        )

    def test_delete_missing_membership_is_idempotent_204_for_existing_user(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.membership_detail_url(user=self.other))

        self.assertEqual(response.status_code, 204)

    def test_delete_last_membership_restores_public_membership(self):
        solo = get_user_model().objects.create_user(username="solo", password="pw")
        set_user_role(solo, UserProfile.ROLE_READER)
        only_group = LibraryGroup.objects.create(name="Only")
        LibraryGroupMembership.objects.create(user=solo, group=only_group)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.membership_detail_url(group=only_group, user=solo))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=solo, group=self.public).exists())

    def test_delete_public_membership_does_not_orphan_user(self):
        public_only = get_user_model().objects.create_user(username="public-only", password="pw")
        set_user_role(public_only, UserProfile.ROLE_READER)
        LibraryGroupMembership.objects.create(user=public_only, group=self.public)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.membership_detail_url(group=self.public, user=public_only))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=public_only, group=self.public).exists()
        )
