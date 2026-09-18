from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession
from core import server_settings
from core.server_installation import get_installation_id
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
        server_settings.set_second_pass_reader_web_client_url("https://reader.example.com/")
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
                "installation_id": str(get_installation_id()),
                "server_name": "Family Library",
                "server_description": "Household books.",
                "server_banner_message": "Maintenance tonight.",
                "advanced_library_groups_enabled": True,
                "second_pass_reader_web_client_url": "https://reader.example.com",
                "marginalia_profile_uri": (
                    "https://secondpasslibrary.local/specs/marginalia/0.1.0"
                ),
                "public_group": {
                    "id": str(public_group.id),
                    "name": "Common Room",
                    "description": "Shared books.",
                },
                "server_version": settings.SECOND_PASS_SERVER_VERSION,
                "server_release_date": settings.SECOND_PASS_SERVER_RELEASE_DATE,
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

    def test_blank_reader_web_client_url_projects_as_null(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/server/info/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["second_pass_reader_web_client_url"])
