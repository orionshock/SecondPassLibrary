from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.groups.services import ensure_user_public_membership
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


User = get_user_model()


class ManagedUsersGroupsPayloadAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group, is_curator=True
        )

    def test_manager_user_list_includes_groups_summary(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        results = cast(list[dict[str, Any]], payload["results"])
        reader_row = next(u for u in results if u["username"] == "reader")
        groups = cast(list[dict[str, Any]], reader_row["groups"])
        self.assertGreaterEqual(len(groups), 1)

        names = {g["name"] for g in groups}
        self.assertIn("Common Room", names)
        self.assertIn("G", names)

        g_row = next(g for g in groups if g["name"] == "G")
        self.assertIn("membership_id", g_row)
        self.assertTrue(g_row["is_curator"])
        self.assertNotIn("membership_role", g_row)
        self.assertFalse(g_row["is_public_group"])

        public_row = next(g for g in groups if g["is_public_group"])
        self.assertIn("membership_id", public_row)
        self.assertFalse(public_row["is_curator"])
        self.assertNotIn("membership_role", public_row)
        self.assertTrue(public_row["is_public_group"])

        # Sanity: does not expose sensitive auth internals.
        self.assertNotIn("is_superuser", reader_row)
        self.assertNotIn("is_staff", reader_row)
        self.assertNotIn("user_permissions", reader_row)
