from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession
from tests.utils.responses import assert_response, response_data_list


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
        self.revoked = UserClientSession.objects.create(
            user=self.user1,
            name="Revoked Reader",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken_revoked"),
            last_seen_at=None,
            expires_at=None,
            revoked_at=timezone.now(),
        )

    @staticmethod
    def bearer_client(token: str) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_anonymous_denied(self):
        r = self.client.get("/api/v1/accounts/me/client-sessions/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        r2 = self.client.delete(f"/api/v1/accounts/me/client-sessions/{self.s1.id}/")
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_only_current_user_active_sessions_and_no_token_hash(self):
        self.client.force_login(self.user1)
        r = assert_response(self.client.get("/api/v1/accounts/me/client-sessions/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = response_data_list(r)
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

        r2 = assert_response(self.client.get("/api/v1/accounts/me/client-sessions/"))
        ids = {row["id"] for row in response_data_list(r2)}
        self.assertNotIn(str(self.s1.id), ids)

    def test_delete_other_users_session_is_404(self):
        self.client.force_login(self.user1)
        r = self.client.delete(f"/api/v1/accounts/me/client-sessions/{self.other.id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_browser_delete_missing_and_revoked_sessions_share_not_found_boundary(self):
        self.client.force_login(self.user1)

        revoked = self.client.delete(
            f"/api/v1/accounts/me/client-sessions/{self.revoked.id}/"
        )
        missing = self.client.delete(
            "/api/v1/accounts/me/client-sessions/"
            "00000000-0000-0000-0000-000000000000/"
        )

        self.assertEqual(revoked.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(revoked.json(), missing.json())

    def test_bearer_cannot_list_client_sessions(self):
        response = self.bearer_client("spl_testtoken_1").get(
            "/api/v1/accounts/me/client-sessions/"
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_bearer_can_revoke_only_its_authenticated_client_session(self):
        bearer = self.bearer_client("spl_testtoken_1")

        response = bearer.delete(
            f"/api/v1/accounts/me/client-sessions/{self.s1.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.s1.refresh_from_db(from_queryset=None)
        self.assertIsNotNone(self.s1.revoked_at)
        rejected = bearer.get("/api/v1/accounts/me/")
        self.assertIn(
            rejected.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_bearer_other_owned_foreign_revoked_and_missing_targets_are_not_found(self):
        bearer = self.bearer_client("spl_testtoken_1")
        target_urls = (
            f"/api/v1/accounts/me/client-sessions/{self.s2.id}/",
            f"/api/v1/accounts/me/client-sessions/{self.other.id}/",
            f"/api/v1/accounts/me/client-sessions/{self.revoked.id}/",
            "/api/v1/accounts/me/client-sessions/"
            "00000000-0000-0000-0000-000000000000/",
        )

        responses = [bearer.delete(url) for url in target_urls]

        self.assertTrue(
            all(
                response.status_code == status.HTTP_404_NOT_FOUND
                for response in responses
            )
        )
        self.assertTrue(
            all(response.json() == responses[0].json() for response in responses)
        )
        self.s2.refresh_from_db(from_queryset=None)
        self.other.refresh_from_db(from_queryset=None)
        self.assertIsNone(self.s2.revoked_at)
        self.assertIsNone(self.other.revoked_at)

    def test_browser_can_revoke_all_owned_active_client_sessions(self):
        revoked_at = self.revoked.revoked_at
        revoked_updated_at = self.revoked.updated_at
        self.client.force_login(self.user1)

        response = self.client.post(
            "/api/v1/accounts/me/client-sessions/revoke-all/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.s1.refresh_from_db(from_queryset=None)
        self.s2.refresh_from_db(from_queryset=None)
        self.other.refresh_from_db(from_queryset=None)
        self.revoked.refresh_from_db(from_queryset=None)
        self.assertIsNotNone(self.s1.revoked_at)
        self.assertIsNotNone(self.s2.revoked_at)
        self.assertIsNone(self.other.revoked_at)
        self.assertEqual(self.revoked.revoked_at, revoked_at)
        self.assertEqual(self.revoked.updated_at, revoked_updated_at)

        active = assert_response(
            self.client.get("/api/v1/accounts/me/client-sessions/")
        )
        self.assertEqual(active.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_list(active), [])

        for token in ("spl_testtoken_1", "spl_testtoken_2"):
            rejected = self.bearer_client(token).get("/api/v1/accounts/me/")
            self.assertIn(
                rejected.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            )

    def test_bearer_cannot_revoke_all_client_sessions(self):
        response = self.bearer_client("spl_testtoken_1").post(
            "/api/v1/accounts/me/client-sessions/revoke-all/"
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.s1.refresh_from_db(from_queryset=None)
        self.s2.refresh_from_db(from_queryset=None)
        self.assertIsNone(self.s1.revoked_at)
        self.assertIsNone(self.s2.revoked_at)

    def test_browser_revoke_all_is_idempotent_with_no_active_sessions(self):
        UserClientSession.objects.filter(user=self.user1, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        self.revoked.refresh_from_db(from_queryset=None)
        existing_revoked_at = self.revoked.revoked_at
        self.client.force_login(self.user1)

        first = self.client.post("/api/v1/accounts/me/client-sessions/revoke-all/")
        second = self.client.post("/api/v1/accounts/me/client-sessions/revoke-all/")

        self.assertEqual(first.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(second.status_code, status.HTTP_204_NO_CONTENT)
        self.revoked.refresh_from_db(from_queryset=None)
        self.assertEqual(self.revoked.revoked_at, existing_revoked_at)
