from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession


User = get_user_model()


class CurrentUserClientSessionsApiTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="pw1")
        self.user2 = User.objects.create_user(username="u2", password="pw2")

        self.s1 = UserClientSession.objects.create(
            user=self.user1,
            name="Reader 1",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken_1"),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        self.s2 = UserClientSession.objects.create(
            user=self.user1,
            name="Reader 2",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken_2"),
            last_seen_at=timezone.now(),
            expires_at=None,
            revoked_at=None,
        )
        self.other = UserClientSession.objects.create(
            user=self.user2,
            name="Other",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken_other"),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )

    def test_anonymous_denied(self):
        r = self.client.get("/api/v1/accounts/me/client-sessions/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        r2 = self.client.delete(f"/api/v1/accounts/me/client-sessions/{self.s1.id}/")
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_only_current_user_active_sessions_and_no_token_hash(self):
        self.client.force_login(self.user1)
        r = cast(Any, self.client.get("/api/v1/accounts/me/client-sessions/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], r.data)
        ids = {row["id"] for row in data}
        self.assertIn(str(self.s1.id), ids)
        self.assertIn(str(self.s2.id), ids)
        self.assertNotIn(str(self.other.id), ids)

        for row in data:
            self.assertFalse("token_hash" in row)

    def test_delete_revokes_own_session_and_removes_from_active_list(self):
        self.client.force_login(self.user1)
        r = self.client.delete(f"/api/v1/accounts/me/client-sessions/{self.s1.id}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.s1.refresh_from_db(from_queryset=None)
        self.assertIsNotNone(self.s1.revoked_at)

        r2 = cast(Any, self.client.get("/api/v1/accounts/me/client-sessions/"))
        ids = {row["id"] for row in cast(list[dict[str, Any]], r2.data)}
        self.assertNotIn(str(self.s1.id), ids)

    def test_delete_other_users_session_is_404(self):
        self.client.force_login(self.user1)
        r = self.client.delete(f"/api/v1/accounts/me/client-sessions/{self.other.id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

