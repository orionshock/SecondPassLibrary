from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework.test import APIClient, APITestCase

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
        client1, key1 = self._make_client_session()
        _, key2 = self._make_client_session()

        session_control.revoke_other_web_sessions(self.user, client1.session)

        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertTrue(
            UserWebSession.objects.filter(user=self.user, session_key=key1).exists()
        )
        self.assertFalse(
            UserWebSession.objects.filter(user=self.user, session_key=key2).exists()
        )

    def test_revoke_other_web_sessions_cleans_stale_tracking_rows(self):
        client1, key1 = self._make_client_session()
        stale_key = "stale-session-key"
        UserWebSession.objects.create(
            user=self.user,
            session_key=stale_key,
            user_agent="",
            ip_address=None,
        )

        self.assertFalse(Session.objects.filter(session_key=stale_key).exists())
        self.assertTrue(UserWebSession.objects.filter(session_key=stale_key).exists())

        session_control.revoke_other_web_sessions(self.user, client1.session)

        self.assertFalse(UserWebSession.objects.filter(session_key=stale_key).exists())

    def test_revoke_other_invalidates_valid_session_without_tracking_row(self):
        current, current_key = self._make_client_session()
        untracked = APIClient()
        self.assertTrue(untracked.login(username="u", password="pw"))
        untracked_key = untracked.session.session_key
        self.assertFalse(
            UserWebSession.objects.filter(session_key=untracked_key).exists()
        )

        session_control.revoke_other_web_sessions(self.user, current.session)

        self.assertTrue(Session.objects.filter(session_key=untracked_key).exists())
        self.assertEqual(current.get("/api/v1/accounts/me/").status_code, 200)
        self.assertIn(untracked.get("/api/v1/accounts/me/").status_code, (401, 403))
        self.assertTrue(Session.objects.filter(session_key=current_key).exists())
        self.assertFalse(Session.objects.filter(session_key=untracked_key).exists())
