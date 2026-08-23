from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession, UserWebSession
from tests.accounts.web_sessions.helpers import authenticated_tracked_client
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class LogoutOtherWebSessionsApiTests(APITestCase):
    def test_authenticated_request_revokes_other_web_sessions_and_keeps_current(self):
        user = User.objects.create_user(username="u", password="pw")
        client1, key1 = authenticated_tracked_client(self, username="u")
        _client2, key2 = authenticated_tracked_client(self, username="u")
        self.assertNotEqual(key1, key2)

        self.assertTrue(
            UserWebSession.objects.filter(user=user, session_key=key1).exists()
        )
        self.assertTrue(
            UserWebSession.objects.filter(user=user, session_key=key2).exists()
        )
        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())

        response = assert_response(
            client1.post(
                "/api/v1/accounts/me/web-sessions/logout-others/",
                data={},
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response_data_dict(response)["message"],
            "Other web sessions logged out.",
        )

        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertTrue(
            UserWebSession.objects.filter(user=user, session_key=key1).exists()
        )
        self.assertFalse(
            UserWebSession.objects.filter(user=user, session_key=key2).exists()
        )

    def test_anonymous_request_is_denied(self):
        client = APIClient()
        response = assert_response(
            client.post(
                "/api/v1/accounts/me/web-sessions/logout-others/",
                data={},
                format="json",
            )
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_client_bearer_cannot_revoke_browser_sessions(self):
        user = User.objects.create_user(username="bearer", password="pw")
        _client1, key1 = authenticated_tracked_client(self, username="bearer")
        _client2, key2 = authenticated_tracked_client(self, username="bearer")
        UserClientSession.objects.create(
            user=user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret("spl_web_session_boundary"),
        )
        bearer = APIClient()

        response = bearer.post(
            "/api/v1/accounts/me/web-sessions/logout-others/",
            data={},
            format="json",
            HTTP_AUTHORIZATION="Bearer spl_web_session_boundary",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())
        self.assertTrue(UserWebSession.objects.filter(session_key=key1).exists())
        self.assertTrue(UserWebSession.objects.filter(session_key=key2).exists())
