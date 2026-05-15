from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile, UserWebSession
from accounts import session_control


User = get_user_model()


class UserWebSessionMiddlewareTests(APITestCase):
    def test_authenticated_request_tracks_user_web_session(self):
        user = User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        r = cast(Any, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        session_key = self.client.session.session_key
        self.assertTrue(session_key)

        tracked = UserWebSession.objects.get(session_key=session_key)
        self.assertEqual(tracked.user.pk, user.pk)

    def test_anonymous_request_does_not_track_user_web_session(self):
        r = cast(Any, self.client.get("/api/v1/accounts/me/"))
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertEqual(UserWebSession.objects.count(), 0)


class SessionControlTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        profile = UserProfile.objects.get(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

    def _make_client_session(self):
        c = APIClient()
        ok = c.login(username="u", password="pw")
        self.assertTrue(ok)
        # Hit an authenticated endpoint to ensure middleware tracks the session.
        r = cast(Any, c.get("/api/v1/accounts/me/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        key = c.session.session_key
        self.assertTrue(key)
        return c, key

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
        self.assertTrue(UserWebSession.objects.filter(user=self.user, session_key=key1).exists())
        self.assertFalse(UserWebSession.objects.filter(user=self.user, session_key=key2).exists())

    def test_revoke_other_web_sessions_cleans_stale_tracking_rows(self):
        _, key1 = self._make_client_session()
        # Create a tracking row for a non-existent session key.
        stale_key = "stale-session-key"
        UserWebSession.objects.create(user=self.user, session_key=stale_key, user_agent="", ip_address=None)

        self.assertFalse(Session.objects.filter(session_key=stale_key).exists())
        self.assertTrue(UserWebSession.objects.filter(session_key=stale_key).exists())

        session_control.revoke_other_web_sessions(self.user, key1)

        self.assertFalse(UserWebSession.objects.filter(session_key=stale_key).exists())


class LogoutOtherWebSessionsApiTests(APITestCase):
    def test_authenticated_request_revokes_other_web_sessions_and_keeps_current(self):
        c1 = APIClient()
        c2 = APIClient()
        user = User.objects.create_user(username="u", password="pw")
        self.assertTrue(c1.login(username="u", password="pw"))
        self.assertTrue(c2.login(username="u", password="pw"))

        # Ensure both sessions are tracked.
        self.assertEqual(cast(Any, c1.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Any, c2.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        key1 = c1.session.session_key
        key2 = c2.session.session_key
        self.assertTrue(key1 and key2 and key1 != key2)

        self.assertTrue(UserWebSession.objects.filter(user=user, session_key=key1).exists())
        self.assertTrue(UserWebSession.objects.filter(user=user, session_key=key2).exists())
        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())

        r = cast(Any, c1.post("/api/v1/accounts/me/web-sessions/logout-others/", data={}, format="json"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(getattr(r, "data", {}).get("message"), "Other web sessions logged out.")

        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertTrue(UserWebSession.objects.filter(user=user, session_key=key1).exists())
        self.assertFalse(UserWebSession.objects.filter(user=user, session_key=key2).exists())

    def test_anonymous_request_is_denied(self):
        c = APIClient()
        r = cast(Any, c.post("/api/v1/accounts/me/web-sessions/logout-others/", data={}, format="json"))
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class PasswordSessionRevocationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")

    def test_self_password_change_revokes_other_sessions_but_keeps_current(self):
        c1 = APIClient()
        c2 = APIClient()
        self.assertTrue(c1.login(username="u", password="pw"))
        self.assertTrue(c2.login(username="u", password="pw"))

        # Ensure both sessions are tracked.
        self.assertEqual(cast(Any, c1.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Any, c2.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        key1 = c1.session.session_key
        key2 = c2.session.session_key
        self.assertTrue(key1 and key2 and key1 != key2)

        r = cast(Any, c1.post(
            "/api/v1/accounts/me/change-password/",
            data={"current_password": "pw", "new_password": "NewPassw0rd!", "confirm_password": "NewPassw0rd!"},
            format="json",
        ))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        # Current session stays valid.
        self.assertEqual(cast(Any, c1.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        current_key = c1.session.session_key
        self.assertTrue(current_key)

        # Other session is revoked.
        r2 = cast(Any, c2.get("/api/v1/accounts/me/"))
        self.assertIn(r2.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        # Note: Django rotates the session key on password change via update_session_auth_hash.
        self.assertTrue(Session.objects.filter(session_key=current_key).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())


class ManagedResetAndDisableSessionRevocationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw", email="owner@example.com")

        self.manager = User.objects.create_user(username="manager", password="pw", email="manager@example.com")
        manager_profile = UserProfile.objects.get(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.target = User.objects.create_user(username="target", password="pw", email="target@example.com")

    def _make_target_sessions(self):
        c1 = APIClient()
        c2 = APIClient()
        self.assertTrue(c1.login(username="target", password="pw"))
        self.assertTrue(c2.login(username="target", password="pw"))
        self.assertEqual(cast(Any, c1.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Any, c2.get("/api/v1/accounts/me/")).status_code, status.HTTP_200_OK)
        k1 = c1.session.session_key
        k2 = c2.session.session_key
        self.assertTrue(k1 and k2 and k1 != k2)
        return k1, k2

    def test_managed_password_reset_revokes_all_target_web_sessions(self):
        k1, k2 = self._make_target_sessions()
        self.assertTrue(Session.objects.filter(session_key=k1).exists())
        self.assertTrue(Session.objects.filter(session_key=k2).exists())

        actor = APIClient()
        self.assertTrue(actor.login(username="owner", password="pw"))
        r = cast(Any, actor.post(f"/api/v1/accounts/users/{self.target.pk}/reset-password/", data={}, format="json"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        self.assertFalse(Session.objects.filter(session_key=k1).exists())
        self.assertFalse(Session.objects.filter(session_key=k2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.target).count(), 0)

    def test_disabling_user_revokes_all_target_web_sessions(self):
        k1, k2 = self._make_target_sessions()

        actor = APIClient()
        self.assertTrue(actor.login(username="manager", password="pw"))
        r = cast(Any, actor.patch(f"/api/v1/accounts/users/{self.target.pk}/", data={"is_active": False}, format="json"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        self.assertFalse(Session.objects.filter(session_key=k1).exists())
        self.assertFalse(Session.objects.filter(session_key=k2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.target).count(), 0)
