from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession


User = get_user_model()


class ShelvesBearerNotEnabledTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Device",
            client_type="test",
            token_hash=hash_client_secret(token),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        self._auth_header = f"Bearer {token}"

    def test_bearer_token_does_not_authenticate_shelves_list(self):
        # Shelves endpoints intentionally do not opt into ClientBearerAuthentication.
        resp = self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth_header)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        # Ensure we did not receive a normal list payload.
        r = resp
        if isinstance(r, Response) and r.data is not None:
            self.assertNotIn("results", r.data)

