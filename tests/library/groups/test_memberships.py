from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup, LibraryGroupMembership
from library.policies import can_curate_group
from tests.library.helpers import set_user_role


class LibraryReWrite2607GroupMembershipApiTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.target = User.objects.create_user(
            username="target",
            password="pw",
            first_name="Target",
            last_name="User",
        )
        self.other = User.objects.create_user(username="other", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        for user in [self.reader, self.target, self.other]:
            set_user_role(user, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.target, group=self.club)
        LibraryGroupMembership.objects.create(user=self.other, group=self.hidden)

    def test_manager_and_owner_can_list_group_memberships(self):
        expected_user_ids = {str(self.reader.profile.id), str(self.target.profile.id)}

        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.get(f"/api/v1/library/groups/{self.club.id}/memberships/")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual({row["user_id"] for row in payload}, expected_user_ids)
                self.assertEqual({row["group_id"] for row in payload}, {str(self.club.id)})

    def test_unauthorized_users_cannot_list_or_manage_memberships(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        list_response = self.client.get(f"/api/v1/library/groups/{self.club.id}/memberships/")
        post_response = self.client.post(
            f"/api/v1/library/groups/{self.club.id}/memberships/",
            _json({"user_id": str(self.other.profile.id)}),
            content_type="application/json",
        )
        patch_response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.target.profile.id}/",
            _json({"is_curator": True}),
            content_type="application/json",
        )
        delete_response = self.client.delete(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.target.profile.id}/"
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_hidden_group_returns_404_before_payload_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            f"/api/v1/library/groups/{self.hidden.id}/memberships/",
            _json({"user_id": "not-a-uuid", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_post_requires_user_id_uuid(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        missing = self.client.post(
            f"/api/v1/library/groups/{self.club.id}/memberships/",
            _json({}),
            content_type="application/json",
        )
        invalid = self.client.post(
            f"/api/v1/library/groups/{self.club.id}/memberships/",
            _json({"user_id": "not-a-uuid"}),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("user_id", missing.json())
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("user_id", invalid.json())

    def test_post_creates_membership_and_returns_uuid_payload(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            f"/api/v1/library/groups/{self.club.id}/memberships/",
            _json(
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
        self.assertEqual(payload["user_id"], str(self.other.profile.id))
        self.assertEqual(payload["user_display"], self.other.get_username())
        self.assertEqual(payload["role"], UserProfile.ROLE_LIBRARIAN)
        self.assertTrue(payload["is_curator"])
        self.assertEqual(payload["group_id"], str(self.club.id))

    def test_post_is_idempotent_and_returns_existing_membership(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        url = f"/api/v1/library/groups/{self.club.id}/memberships/"
        body = _json({"user_id": str(self.target.profile.id), "is_curator": True})

        first = self.client.post(url, body, content_type="application/json")
        second = self.client.post(url, body, content_type="application/json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(
            LibraryGroupMembership.objects.filter(user=self.target, group=self.club).count(),
            1,
        )

    def test_patch_updates_role_and_is_curator(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.target.profile.id}/",
            _json({"role": UserProfile.ROLE_LIBRARIAN, "is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], UserProfile.ROLE_LIBRARIAN)
        self.assertTrue(response.json()["is_curator"])
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.role, UserProfile.ROLE_LIBRARIAN)

    def test_patch_rejects_unknown_and_invalid_role(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        url = f"/api/v1/library/groups/{self.club.id}/memberships/{self.target.profile.id}/"

        unknown = self.client.patch(
            url,
            _json({"unknown": "field"}),
            content_type="application/json",
        )
        invalid_role = self.client.patch(
            url,
            _json({"role": ""}),
            content_type="application/json",
        )

        self.assertEqual(unknown.status_code, 400)
        self.assertIn("unknown", unknown.json())
        self.assertEqual(invalid_role.status_code, 400)
        self.assertIn("role", invalid_role.json())

    def test_patch_missing_membership_returns_404(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.other.profile.id}/",
            _json({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_removes_membership(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.target.profile.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            LibraryGroupMembership.objects.filter(user=self.target, group=self.club).exists()
        )

    def test_delete_missing_membership_is_idempotent_204_for_existing_user(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(
            f"/api/v1/library/groups/{self.club.id}/memberships/{self.other.profile.id}/"
        )

        self.assertEqual(response.status_code, 204)

    def test_delete_last_membership_restores_public_membership(self):
        solo = get_user_model().objects.create_user(username="solo", password="pw")
        set_user_role(solo, UserProfile.ROLE_READER)
        only_group = LibraryGroup.objects.create(name="Only")
        LibraryGroupMembership.objects.create(user=solo, group=only_group)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(
            f"/api/v1/library/groups/{only_group.id}/memberships/{solo.profile.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=solo, group=self.public).exists())

    def test_delete_public_membership_does_not_orphan_user(self):
        public_only = get_user_model().objects.create_user(username="public-only", password="pw")
        set_user_role(public_only, UserProfile.ROLE_READER)
        LibraryGroupMembership.objects.create(user=public_only, group=self.public)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(
            f"/api/v1/library/groups/{self.public.id}/memberships/{public_only.profile.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=public_only, group=self.public).exists()
        )

    def test_public_curator_membership_does_not_grant_curation(self):
        LibraryGroupMembership.objects.create(user=self.target, group=self.public)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.public.id}/memberships/{self.target.profile.id}/",
            _json({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(can_curate_group(user=self.target, group=self.public))

    def test_get_list_does_not_expose_unrelated_group_memberships(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/memberships/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.other.profile.id), {row["user_id"] for row in response.json()})


def _json(data: dict) -> str:
    return json.dumps(data)
