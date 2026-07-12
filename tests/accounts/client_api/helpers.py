from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


User = get_user_model()


class ClientApiTestCase(APITestCase):
    def setUp(self):
        self.bootstrap_owner = User.objects.create_superuser(
            username="bootstrap-owner",
            email="bootstrap-owner@example.com",
            password="pw",
        )


def post_login_request(client):
    return client.post(
        "/api/v1/client-api/login-requests/",
        data={"client_name": "Second Pass Reader", "client_type": "reader"},
        format="json",
    )
