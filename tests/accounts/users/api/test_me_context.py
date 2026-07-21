from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
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
        self.assertNotIn("is_owner", data)
        self.assertNotIn("must_change_password", data)
        self.assertNotIn("advanced_library_groups_enabled", data)
        self.assertNotIn("can_access_django_admin", data)
        self.assertEqual(data["banner_text"], "")
        self.assertNotIn("id", data)
        self.assertNotIn("capabilities", data)

        groups = payload_list(data, "groups")
        self.assertGreaterEqual(len(groups), 1)
        public_groups = [g for g in groups if g["is_public_group"]]
        self.assertEqual(len(public_groups), 1)
        self.assertTrue(public_groups[0]["is_public_group"])
        self.assertNotIn("is_curator", public_groups[0])
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
            "groups",
            "banner_text",
        ):
            self.assertIn(key, data)
        self.assertNotIn("must_change_password", data)
        self.assertNotIn("is_owner", data)
        self.assertNotIn("advanced_library_groups_enabled", data)
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
        self.assertNotIn("is_owner", data)
        self.assertEqual(data["role"], UserProfile.ROLE_MANAGER)
        self.assertNotIn("capabilities", data)

    def test_me_owner_payload_uses_owner_flag_without_capabilities(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertTrue(data["is_owner"])
        self.assertNotIn("can_access_django_admin", data)
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
        self.assertNotIn("is_owner", data)
        self.assertNotIn("capabilities", data)

        groups = payload_list(data, "groups")
        group_row = next(row for row in groups if row["name"] == "Fantasy Club")
        self.assertTrue(group_row["is_curator"])
        self.assertNotIn("curated_group_ids", data)

    def test_me_includes_must_change_password_only_when_true(self):
        profile = UserProfile.objects.get(user=self.reader)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password"])

        self.client.login(username="reader", password="pw")
        data = response_data_dict(
            assert_response(self.client.get("/api/v1/accounts/me/"))
        )

        self.assertTrue(data["must_change_password"])

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True)
    def test_me_owner_includes_django_admin_capability_when_enabled(self):
        self.client.login(username="owner", password="pw")
        data = response_data_dict(
            assert_response(self.client.get("/api/v1/accounts/me/"))
        )

        self.assertTrue(data["can_access_django_admin"])

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=False)
    def test_me_owner_omits_django_admin_capability_when_disabled(self):
        self.client.login(username="owner", password="pw")
        data = response_data_dict(
            assert_response(self.client.get("/api/v1/accounts/me/"))
        )

        self.assertNotIn("can_access_django_admin", data)

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True)
    def test_me_non_owner_omits_django_admin_capability_when_enabled(self):
        self.client.login(username="manager", password="pw")
        data = response_data_dict(
            assert_response(self.client.get("/api/v1/accounts/me/"))
        )

        self.assertNotIn("can_access_django_admin", data)
