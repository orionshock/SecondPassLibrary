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
        self.assertEqual(resp.json()["server_name"], "Second Pass Library")

        resp = self.client.patch(
            "/api/v1/server/settings/",
            data={"server_name": "My Library", "server_description": "Private."},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["server_name"], "My Library")
        self.assertEqual(data["server_description"], "Private.")

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

        discovery = self.client.get("/api/v1/client-api/discovery/")
        self.assertEqual(discovery.status_code, 200)
        payload = discovery.json()
        self.assertEqual(payload["server_name"], "My Library")
        self.assertEqual(payload["server_description"], "Private.")
