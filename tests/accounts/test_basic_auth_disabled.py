from __future__ import annotations

import base64

from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class BasicAuthenticationDisabledTests(TestCase):
    def setUp(self):
        self.password = "correct-horse-battery-staple"
        self.user = User.objects.create_user(
            username="basic-disabled",
            password=self.password,
        )

    def _basic_header(self) -> str:
        raw = f"{self.user.username}:{self.password}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def test_valid_basic_authorization_header_does_not_authenticate(self):
        response = self.client.get(
            "/api/v1/accounts/me/",
            HTTP_AUTHORIZATION=self._basic_header(),
        )

        self.assertEqual(response.status_code, 403)
