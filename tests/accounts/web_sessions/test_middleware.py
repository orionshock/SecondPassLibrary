from __future__ import annotations

from django.contrib.auth import get_user_model
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

    def test_anonymous_request_does_not_track_user_web_session(self):
        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(UserWebSession.objects.count(), 0)
