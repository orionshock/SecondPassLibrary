"""Tests for Product UI error page behavior."""
from pathlib import Path

from django.test import override_settings

from accounts.models import UserProfile
from accounts.services import get_or_create_profile
from tests.core.product_ui.helpers import ProductUiTestCase


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ProductUiErrorPageTests(ProductUiTestCase):
    """Test styled Product UI error pages under non-debug settings."""

    def test_error_templates_include_styled_page_copy(self):
        template_500 = Path("web/templates/500.html").read_text(encoding="utf-8")
        error_base = Path("web/templates/web/error_base.html").read_text(encoding="utf-8")

        self.assertIn("Something went wrong", template_500)
        self.assertIn("The server hit an unexpected problem.", template_500)
        self.assertIn('href="/dashboard/"', error_base)
        self.assertIn("Go to dashboard", error_base)

    def test_missing_route_renders_styled_404(self):
        response = self.client.get("/missing-product-ui-route/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(
            response,
            "That page does not exist or is not available.",
            status_code=404,
        )
        self.assertContains(response, 'href="/dashboard/"', status_code=404)
        self.assertContains(response, "Go to dashboard", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)
        self.assertNotContains(response, "Request Method", status_code=404)

    def test_app_route_renders_styled_404(self):
        response = self.client.get("/app/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, 'href="/dashboard/"', status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_malformed_object_route_renders_styled_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/library/books/not-a-uuid/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, 'href="/dashboard/"', status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_server_settings_forbidden_renders_styled_403(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.get("/server/")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Not allowed", status_code=403)
        self.assertContains(
            response,
            "You do not have permission to view this page.",
            status_code=403,
        )
        self.assertContains(response, 'href="/dashboard/"', status_code=403)
        self.assertNotContains(response, "Traceback", status_code=403)
