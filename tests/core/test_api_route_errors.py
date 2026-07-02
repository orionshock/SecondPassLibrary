from __future__ import annotations

from django.test import TestCase, override_settings


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ApiRouteErrorTests(TestCase):
    def test_api_v1_route_miss_returns_json_404(self):
        response = self.client.get("/api/v1/not-a-route/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_api_route_miss_returns_json_404(self):
        response = self.client.get("/api/not-a-route/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_api_malformed_uuid_route_miss_returns_json_404(self):
        response = self.client.get(
            "/api/v1/reading/books/not-a-uuid/active-session/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_product_ui_route_miss_returns_styled_html_404(self):
        response = self.client.get("/not-a-real-page/")

        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, 'href="/dashboard/"', status_code=404)

    def test_removed_app_route_remains_styled_html_404(self):
        response = self.client.get("/app/")

        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, 'href="/dashboard/"', status_code=404)
