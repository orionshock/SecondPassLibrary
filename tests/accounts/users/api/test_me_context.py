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
    def test_reader_me_payload_is_exact_and_excludes_server_authority_context(self):
        server_settings.set_server_banner_message("Maintenance tonight.")
        server_settings.enable_advanced_library_groups()
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/me/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(
            set(data),
            {
                "username",
                "email",
                "first_name",
                "last_name",
                "profile_id",
                "role",
                "groups",
            },
        )
        self.assertEqual(data["username"], "reader")
        self.assertEqual(data["email"], "reader@example.com")
        self.assertEqual(
            data["profile_id"], str(UserProfile.objects.get(user=self.reader).id)
        )
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertEqual(
            payload_list(data, "groups"),
            [
                {
                    "id": str(self.public.id),
                    "name": self.public.name,
                    "is_public_group": True,
                }
            ],
        )

    def test_me_role_and_owner_deltas(self):
        cases = (
            ("manager", UserProfile.ROLE_MANAGER, False),
            ("owner", UserProfile.ROLE_READER, True),
        )
        for username, expected_role, expected_owner in cases:
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = assert_response(self.client.get("/api/v1/accounts/me/"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response_data_dict(response)
                self.assertEqual(data["role"], expected_role)
                self.assertEqual(data.get("is_owner", False), expected_owner)

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

    def test_me_django_admin_capability_matrix(self):
        cases = (
            ("owner", True, True),
            ("owner", False, False),
            ("manager", True, False),
        )
        for username, admin_enabled, expected_capability in cases:
            with self.subTest(username=username, admin_enabled=admin_enabled):
                self.client.logout()
                with override_settings(
                    SECOND_PASS_ENABLE_DJANGO_ADMIN=admin_enabled
                ):
                    self.client.login(username=username, password="pw")
                    data = response_data_dict(
                        assert_response(self.client.get("/api/v1/accounts/me/"))
                    )
                self.assertEqual(
                    data.get("can_access_django_admin", False),
                    expected_capability,
                )
