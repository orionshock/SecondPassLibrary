from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from core import server_settings


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
        self.assertEqual(data["server_name"], "Second Pass Library")
        self.assertEqual(data["server_banner_message"], "")
        self.assertEqual(data["public_group_name"], "Common Room")
        self.assertFalse(data["advanced_library_groups_enabled"])

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
        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"server_name": "   "},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertIn("server_name", payload)

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

    def test_well_known_secondpass_returns_compact_server_discovery(self):
        response = self.client.get("/.well-known/secondpass")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "server_name": "Second Pass Library",
                "server_description": "",
                "server_version": "0.1.0-dev",
                "server_release": "pre-release",
                "server_release_date": "2026-07-03",
                "api_base_url": "http://testserver/api/v1/",
            },
        )

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
        self.assertEqual(payload["server_description"], "Private.")
        self.assertEqual(payload["server_version"], "0.1.0-dev")
        self.assertEqual(payload["server_release"], "pre-release")
        self.assertEqual(payload["server_release_date"], "2026-07-03")
        self.assertEqual(payload["api_base_url"], "http://testserver/api/v1/")
        self.assertNotIn("client_api", payload)
        self.assertNotIn("login_request_endpoint", payload)
        self.assertNotIn("authorize_url", payload)
        self.assertNotIn("poll_endpoint_template", payload)
        self.assertEqual(
            set(payload),
            {
                "server_name",
                "server_description",
                "server_version",
                "server_release",
                "server_release_date",
                "api_base_url",
            },
        )

        discovery = self.client.get("/api/v1/client-api/discovery/")
        self.assertEqual(discovery.status_code, 200)
        payload = discovery.json()
        self.assertEqual(payload["server_name"], "My Library")
        self.assertEqual(payload["server_description"], "Private.")
