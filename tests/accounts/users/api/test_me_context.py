from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from accounts.models import UserProfile
from core import server_settings
from library.models import LibraryGroup, LibraryGroupMembership
from tests.accounts.users.helpers import ManagedUsersApiTestMixin
from tests.utils.responses import assert_response, payload_list, response_data_dict


pytestmark = [pytest.mark.integration]
User = get_user_model()


class ManagedUsersMeContextAPITest(ManagedUsersApiTestMixin):
    def test_me_endpoint_still_works(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["username"], "reader")
        self.assertEqual(
            data["profile_id"], str(UserProfile.objects.get(user=self.reader).id)
        )
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertFalse(data["is_owner"])
        self.assertFalse(data["advanced_library_groups_enabled"])
        self.assertEqual(data["banner_text"], "")
        self.assertNotIn("id", data)
        self.assertNotIn("capabilities", data)

        groups = payload_list(data, "groups")
        self.assertGreaterEqual(len(groups), 1)
        public_groups = [g for g in groups if g["is_public_group"]]
        self.assertEqual(len(public_groups), 1)
        self.assertTrue(public_groups[0]["is_public_group"])
        self.assertFalse(public_groups[0]["is_curator"])
        self.assertNotIn("membership_role", public_groups[0])
        self.assertNotIn("curated_group_ids", data)

    def test_me_includes_refreshable_server_context(self):
        server_settings.set_server_banner_message("Maintenance tonight.")

        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        for key in (
            "username",
            "email",
            "first_name",
            "last_name",
            "profile_id",
            "role",
            "must_change_password",
            "is_owner",
            "groups",
            "advanced_library_groups_enabled",
            "banner_text",
        ):
            self.assertIn(key, data)
        self.assertFalse(data["advanced_library_groups_enabled"])
        self.assertEqual(data["banner_text"], "Maintenance tonight.")
        self.assertNotIn("capabilities", data)
        self.assertNotIn("routes", data)
        self.assertNotIn("route_manifest", data)

    def test_me_advanced_library_groups_enabled_reflects_server_setting(self):
        server_settings.enable_advanced_library_groups()

        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertTrue(data["advanced_library_groups_enabled"])

    def test_me_manager_payload_uses_role_without_capabilities(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertFalse(data["is_owner"])
        self.assertEqual(data["role"], UserProfile.ROLE_MANAGER)
        self.assertNotIn("capabilities", data)

    def test_me_owner_payload_uses_owner_flag_without_capabilities(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertTrue(data["is_owner"])
        self.assertNotIn("capabilities", data)

    def test_me_allows_multiple_owner_flags(self):
        User.objects.create_superuser(
            username="owner2", email="owner2@example.com", password="pw"
        )

        self.client.login(username="owner2", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["username"], "owner2")
        self.assertTrue(data["is_owner"])
        self.assertNotIn("capabilities", data)

    def test_me_curator_reader_has_scoped_group_presentation_power(self):
        group = LibraryGroup.objects.create(name="Fantasy Club")
        LibraryGroupMembership.objects.create(
            user=self.reader,
            group=group,
            is_curator=True,
        )

        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertFalse(data["is_owner"])
        self.assertNotIn("capabilities", data)

        groups = payload_list(data, "groups")
        group_row = next(row for row in groups if row["name"] == "Fantasy Club")
        self.assertTrue(group_row["is_curator"])
        self.assertNotIn("curated_group_ids", data)
