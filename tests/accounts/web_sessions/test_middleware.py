from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserWebSession
from tests.utils.responses import assert_response


User = get_user_model()


class UserWebSessionMiddlewareTests(APITestCase):
    def test_authenticated_request_tracks_user_web_session(self):
        user = User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session_key = self.client.session.session_key
        self.assertTrue(session_key)

        tracked = UserWebSession.objects.get(session_key=session_key)
        self.assertEqual(tracked.user.pk, user.pk)

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["10.0.0.2"],
    )
    def test_tracks_effective_client_ip_from_trusted_proxy(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                REMOTE_ADDR="10.0.0.2",
                HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.2",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tracked = UserWebSession.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(tracked.ip_address, "203.0.113.10")

    def test_tracks_valid_remote_address_and_ignores_untrusted_forwarding(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                REMOTE_ADDR="2001:0db8:0:0::1",
                HTTP_X_FORWARDED_FOR="203.0.113.10",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tracked = UserWebSession.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(tracked.ip_address, "2001:db8::1")

    def test_anonymous_request_does_not_track_user_web_session(self):
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(UserWebSession.objects.count(), 0)

    def test_session_generation_lookup_failure_fails_closed_with_bounded_response(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        with patch(
            "accounts.middleware.UserProfile.objects.values_list",
            side_effect=RuntimeError("database detail"),
        ):
            response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertNotIn("database detail", response.content.decode())
