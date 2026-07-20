from __future__ import annotations

import importlib

from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, clear_url_caches, resolve, set_urlconf

import secondpass.urls


def _reload_project_urls():
    clear_url_caches()
    set_urlconf(None)
    return importlib.reload(secondpass.urls)


class DjangoAdminUrlGatingTests(SimpleTestCase):
    def tearDown(self):
        _reload_project_urls()
        super().tearDown()

    def test_admin_route_is_not_registered_by_default(self):
        _reload_project_urls()

        with self.assertRaises(Resolver404):
            resolve("/admin/")

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=False)
    def test_admin_route_is_not_registered_when_disabled(self):
        _reload_project_urls()

        with self.assertRaises(Resolver404):
            resolve("/admin/")

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True)
    def test_admin_route_is_registered_when_explicitly_enabled(self):
        _reload_project_urls()

        match = resolve("/admin/")

        self.assertEqual(match.url_name, "index")

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=False)
    def test_product_ui_and_api_routes_remain_registered_when_admin_disabled(self):
        _reload_project_urls()

        product_match = resolve("/")
        api_match = resolve("/api/v1/health/")

        self.assertEqual(product_match.url_name, "react_app")
        self.assertEqual(api_match.namespace, "core")
