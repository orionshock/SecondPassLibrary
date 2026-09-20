from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from core import server_settings
from core.server_identity import get_server_id


User = get_user_model()


class ServerIdentitySettingsTests(TestCase):
    def setUp(self):
        cache.clear()
        server_settings.clear_server_settings_cache()

    def test_get_server_name_default(self):
        self.assertEqual(server_settings.get_server_name(), "Second Pass Library")

    def test_set_server_name_requires_non_empty(self):
        with self.assertRaises(ValueError):
            server_settings.set_server_name("   ")

    def test_owner_only_server_settings_api(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        manager = User.objects.create_user(username="manager", password="pw")

        self.client.force_login(manager)
        resp = self.client.get("/api/v1/server/settings/")
        self.assertEqual(resp.status_code, 403)

        self.client.force_login(owner)
        resp = self.client.get("/api/v1/server/settings/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        server_id = data["server_id"]
        self.assertEqual(uuid.UUID(server_id), get_server_id())
        self.assertEqual(data["server_name"], "Second Pass Library")
        self.assertEqual(data["server_banner_message"], "")
        self.assertEqual(data["public_group_name"], "Common Room")
        self.assertFalse(data["advanced_library_groups_enabled"])
        self.assertEqual(data["second_pass_reader_web_client_url"], "")
        self.assertFalse(data["second_pass_reader_web_client_url_locked"])

        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "server_name": "My Library",
                "server_description": "Private.",
                "server_banner_message": "  Maintenance tonight.  ",
                "public_group_name": "Reading Room",
                "public_group_description": "Shared books.",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["server_id"], server_id)
        self.assertEqual(data["server_name"], "My Library")
        self.assertEqual(data["server_description"], "Private.")
        self.assertEqual(data["server_banner_message"], "Maintenance tonight.")
        self.assertEqual(data["public_group_name"], "Reading Room")
        self.assertEqual(data["public_group_description"], "Shared books.")
        self.assertFalse(data["advanced_library_groups_enabled"])

        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"server_banner_message": "   "},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["server_banner_message"], "")

    def test_reader_web_client_setting_normalizes_and_reports_environment_lock(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)

        response = self.client.patch(
            "/api/v1/server/settings/",
            data={"second_pass_reader_web_client_url": " http://localhost:5173/ "},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["second_pass_reader_web_client_url"], "http://localhost:5173"
        )
        self.assertFalse(response.json()["second_pass_reader_web_client_url_locked"])

        response = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "second_pass_reader_web_client_url": (
                    "https://reader.example.com/app?theme=dark#home"
                )
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["second_pass_reader_web_client_url"],
            "https://reader.example.com",
        )

        with override_settings(
            SECOND_PASS_READER_WEB_CLIENT_URL="https://env-reader.example.com/setup"
        ):
            server_settings.synchronize_deployment_server_settings()
            response = self.client.get("/api/v1/server/settings/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["second_pass_reader_web_client_url"],
                "https://env-reader.example.com",
            )
            self.assertTrue(response.json()["second_pass_reader_web_client_url_locked"])

            response = self.client.patch(
                "/api/v1/server/settings/",
                data={"second_pass_reader_web_client_url": ""},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("second_pass_reader_web_client_url", response.json())

    def test_public_group_description_uses_shared_rich_text_contract(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)

        accepted = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "public_group_description": (
                    '<p class="no">Shared <em>books</em></p><script>bad()</script>'
                )
            },
            content_type="application/json",
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(
            accepted.json()["public_group_description"],
            "<p>Shared <em>books</em></p>",
        )

        rejected = self.client.patch(
            "/api/v1/server/settings/",
            data={"public_group_description": "x" * 25_001},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("public_group_description", rejected.json())

    def test_advanced_library_groups_enable_endpoint_is_one_way(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        manager = User.objects.create_user(username="manager", password="pw")

        self.client.force_login(manager)
        resp = self.client.post(
            "/api/v1/server/settings/advanced-library-groups/enable/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(server_settings.advanced_library_groups_enabled())

        self.client.force_login(owner)
        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"advanced_library_groups_enabled": True},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(server_settings.advanced_library_groups_enabled())

        resp = self.client.post(
            "/api/v1/server/settings/advanced-library-groups/enable/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["advanced_library_groups_enabled"])

        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"advanced_library_groups_enabled": False},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(server_settings.advanced_library_groups_enabled())

    def test_patch_rejects_unknown_fields(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"server_name": "My Library", "public_group_id": "nope"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertEqual(payload.get("detail"), "Unknown fields.")
        self.assertEqual(payload.get("fields"), ["public_group_id"])

    def test_patch_rejects_blank_server_name(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        server_settings.set_server_description("Original description")
        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "server_name": "   ",
                "server_description": "Must not persist",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertIn("server_name", payload)
        self.assertEqual(
            server_settings.get_server_description(),
            "Original description",
        )

    def test_patch_rejects_overlong_server_banner_message(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"server_banner_message": "x" * 501},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertIn("server_banner_message", payload)

    def test_patch_sanitizes_server_identity_html_before_returning_it(self):
        owner = User.objects.create_user(
            username="owner-rich-text",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)

        response = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "server_description": (
                    '<p class="lead">Private <b>library</b></p>'
                    '<script>alert("no")</script>'
                ),
                "server_banner_message": (
                    '<ol><li onclick="alert(1)">Maintenance</li></ol>'
                ),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["server_description"],
            "<p>Private <b>library</b></p>",
        )
        self.assertEqual(
            response.json()["server_banner_message"],
            "<ol><li>Maintenance</li></ol>",
        )

    @override_settings(SECOND_PASS_LIBRARY_URLS=["https://private.home.example"])
    def test_well_known_secondpass_returns_compact_server_discovery(self):
        response = self.client.get("/.well-known/secondpass")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "server_id": str(get_server_id()),
                "server_name": "Second Pass Library",
                "server_description": "",
                "server_version": settings.SECOND_PASS_SERVER_VERSION,
                "server_release_date": settings.SECOND_PASS_SERVER_RELEASE_DATE,
            },
        )
        payload = response.json()
        self.assertNotIn("server_release", payload)
        self.assertNotIn("banner_text", payload)
        self.assertNotIn("advanced_library_groups_enabled", payload)
        self.assertNotIn("capabilities", payload)
        self.assertNotIn("client_api", payload)
        self.assertNotIn("routes", payload)
        self.assertNotIn("route_manifest", payload)
        self.assertNotIn("login_request_endpoint", payload)
        self.assertNotIn("authorize_url", payload)
        self.assertNotIn("poll_endpoint_template", payload)

    def test_well_known_discovery_rejects_unsafe_methods(self):
        response = self.client.post("/.well-known/secondpass")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, HEAD")

    def test_discovery_includes_server_identity(self):
        owner = User.objects.create_user(
            username="owner",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        self.client.patch(
            "/api/v1/server/settings/",
            data={"server_name": "My Library", "server_description": "Private."},
            content_type="application/json",
        )

        well_known = self.client.get("/.well-known/secondpass")
        self.assertEqual(well_known.status_code, 200)
        payload = well_known.json()
        self.assertEqual(payload["server_name"], "My Library")
        self.assertEqual(payload["server_id"], str(get_server_id()))
        self.assertEqual(payload["server_description"], "Private.")
        self.assertEqual(payload["server_version"], settings.SECOND_PASS_SERVER_VERSION)
        self.assertEqual(
            payload["server_release_date"], settings.SECOND_PASS_SERVER_RELEASE_DATE
        )
        self.assertNotIn("api_base_url", payload)
        self.assertNotIn("server_urls", payload)
        self.assertNotIn("banner_text", payload)
        self.assertNotIn("advanced_library_groups_enabled", payload)
        self.assertNotIn("capabilities", payload)
        self.assertNotIn("client_api", payload)
        self.assertNotIn("routes", payload)
        self.assertNotIn("route_manifest", payload)
        self.assertNotIn("login_request_endpoint", payload)
        self.assertNotIn("authorize_url", payload)
        self.assertNotIn("poll_endpoint_template", payload)
        self.assertEqual(
            set(payload),
            {
                "server_id",
                "server_name",
                "server_description",
                "server_version",
                "server_release_date",
            },
        )

        discovery = self.client.get("/api/v1/client-api/discovery/")
        self.assertEqual(discovery.status_code, 200)
        payload = discovery.json()
        self.assertEqual(payload["server_name"], "My Library")
        self.assertEqual(payload["server_description"], "Private.")
