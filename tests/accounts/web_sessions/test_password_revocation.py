from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework import status
from rest_framework.test import APITestCase

from tests.accounts.web_sessions.helpers import authenticated_tracked_client
from tests.utils.responses import assert_response


User = get_user_model()


class PasswordSessionRevocationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u",
            password="pw",
            email="u@example.com",
        )

    def test_self_password_change_revokes_other_sessions_but_keeps_current(self):
        client1, _key1 = authenticated_tracked_client(self, username="u")
        client2, key2 = authenticated_tracked_client(self, username="u")

        response = assert_response(
            client1.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "pw",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "NewPassw0rd!",
                },
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            assert_response(client1.get("/api/v1/accounts/me/")).status_code,
            status.HTTP_200_OK,
        )
        current_key = client1.session.session_key
        self.assertTrue(current_key)

        response2 = assert_response(client2.get("/api/v1/accounts/me/"))
        self.assertIn(
            response2.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertTrue(Session.objects.filter(session_key=current_key).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
