from __future__ import annotations

from django.test import TestCase, override_settings


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ApiRouteErrorTests(TestCase):
    def test_api_route_misses_return_the_json_404_contract(self):
        for path in (
            "/api/v1/not-a-route/",
            "/api/not-a-route/",
            "/api/v1/marginalia/books/not-a-uuid/active-session/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.headers["Content-Type"],
                    "application/json",
                )
                self.assertEqual(response.json(), {"detail": "Not found."})
