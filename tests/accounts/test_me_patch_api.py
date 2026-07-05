from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from tests.utils.responses import assert_response, payload_dict, response_data_dict


User = get_user_model()


class CurrentUserMePatchAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

    def test_anonymous_patch_denied(self):
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"email": "x@example.com"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_patch_email_first_last_and_response_shape_matches_me(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={
                    "email": "new@example.test",
                    "first_name": "R",
                    "last_name": "Eader",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)

        # Same /me shape (bootstrap payload keys).
        for key in (
            "username",
            "email",
            "profile_id",
            "role",
            "is_owner",
            "advanced_library_groups_enabled",
            "banner_text",
            "groups",
        ):
            self.assertIn(key, data)
        self.assertNotIn("capabilities", data)
        self.assertNotIn("curated_group_ids", data)

        self.assertEqual(data["username"], "reader")
        self.assertEqual(data["email"], "new@example.test")
        self.assertEqual(data["profile_id"], str(cast(Any, self.user).profile.id))
        self.assertNotIn("id", data)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.test")
        self.assertEqual(self.user.first_name, "R")
        self.assertEqual(self.user.last_name, "Eader")

    def test_cannot_patch_role(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(payload_dict(data, "error")["code"], "UNSAFE_FIELD")

    def test_cannot_patch_is_active(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(payload_dict(data, "error")["code"], "UNSAFE_FIELD")

    def test_cannot_patch_username(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"username": "newname"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(payload_dict(data, "error")["code"], "UNSAFE_FIELD")

    def test_cannot_patch_password(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"password": "nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(payload_dict(data, "error")["code"], "UNSAFE_FIELD")
