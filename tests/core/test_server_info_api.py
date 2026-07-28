from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from core import server_settings
from library.groups.public_services import configure_public_group


User = get_user_model()


class ServerInfoApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        server_settings.clear_server_settings_cache()
        self.user = User.objects.create_user(username="reader", password="pw")

    def test_anonymous_request_is_rejected(self):
        response = self.client.get("/api/v1/server/info/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_session_request_returns_authenticated_server_context(self):
        server_settings.set_server_name("Family Library")
        server_settings.set_server_description("Household books.")
        server_settings.set_server_banner_message("Maintenance tonight.")
        server_settings.set_advanced_library_groups_enabled(True)
        server_settings.set_reading_client_base_url("https://reader.example.com/")
        public_group = configure_public_group(
            name="Common Room",
            description="Shared books.",
        )
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/server/info/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "server_name": "Family Library",
                "server_description": "Household books.",
                "server_banner_message": "Maintenance tonight.",
                "advanced_library_groups_enabled": True,
                "reading_client_base_url": "https://reader.example.com",
                "public_group": {
                    "id": str(public_group.id),
                    "name": "Common Room",
                    "description": "Shared books.",
                },
                "server_version": "0.1.0-dev",
                "server_release_date": "2026-07-19",
            },
        )
        for excluded in (
            "server_release",
            "api_base_url",
            "username",
            "role",
            "memberships",
            "can_access_django_admin",
            "capabilities",
        ):
            self.assertNotIn(excluded, response.json())

    def test_bearer_request_is_allowed(self):
        token = "spl_server_info_test"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        api = APIClient()

        response = api.get(
            "/api/v1/server/info/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["server_name"], "Second Pass Library")

    def test_endpoint_is_read_only(self):
        self.client.force_login(self.user)

        for method in ("post", "patch", "put", "delete"):
            response = getattr(self.client, method)(
                "/api/v1/server/info/",
                data={},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_blank_reading_client_url_projects_as_null(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/server/info/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["reading_client_base_url"])
