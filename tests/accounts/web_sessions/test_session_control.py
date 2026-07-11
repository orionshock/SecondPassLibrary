from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework.test import APITestCase

from accounts import session_control
from accounts.models import UserProfile, UserWebSession
from tests.accounts.web_sessions.helpers import authenticated_tracked_client


User = get_user_model()


class SessionControlTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        profile = UserProfile.objects.get(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

    def _make_client_session(self):
        return authenticated_tracked_client(self, username="u")

    def test_revoke_all_web_sessions_deletes_sessions_and_tracking(self):
        _, key1 = self._make_client_session()
        _, key2 = self._make_client_session()
        self.assertNotEqual(key1, key2)

        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.user).count(), 2)

        session_control.revoke_all_web_sessions(self.user)

        self.assertFalse(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.user).count(), 0)

    def test_revoke_other_web_sessions_preserves_current(self):
        _, key1 = self._make_client_session()
        _, key2 = self._make_client_session()

        session_control.revoke_other_web_sessions(self.user, key1)

        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertTrue(
            UserWebSession.objects.filter(user=self.user, session_key=key1).exists()
        )
        self.assertFalse(
            UserWebSession.objects.filter(user=self.user, session_key=key2).exists()
        )

    def test_revoke_other_web_sessions_cleans_stale_tracking_rows(self):
        _, key1 = self._make_client_session()
        stale_key = "stale-session-key"
        UserWebSession.objects.create(
            user=self.user,
            session_key=stale_key,
            user_agent="",
            ip_address=None,
        )

        self.assertFalse(Session.objects.filter(session_key=stale_key).exists())
        self.assertTrue(UserWebSession.objects.filter(session_key=stale_key).exists())

        session_control.revoke_other_web_sessions(self.user, key1)

        self.assertFalse(UserWebSession.objects.filter(session_key=stale_key).exists())
