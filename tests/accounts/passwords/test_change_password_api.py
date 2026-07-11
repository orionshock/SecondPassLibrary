from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from tests.utils.responses import assert_response


User = get_user_model()


class ChangePasswordApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )
        profile = UserProfile.objects.get(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.login(username="u", password="pw")

    def test_change_password_requires_current_password(self):
        response = assert_response(
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "wrong",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "NewPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_fails_when_confirm_password_does_not_match(self):
        response = assert_response(
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "pw",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "DifferentPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_updates_password_and_clears_must_change_password(self):
        response = assert_response(
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "pw",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "NewPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        me = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)

        profile = UserProfile.objects.get(user=self.user)
        self.assertFalse(profile.must_change_password)

        self.client.logout()
        ok = self.client.login(username="u", password="NewPassw0rd!")
        self.assertTrue(ok)
