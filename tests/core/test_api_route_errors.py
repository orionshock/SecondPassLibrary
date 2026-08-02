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
            "/api/v1/marginalia/books/not-a-uuid/active-session/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"detail": "Not found."})
