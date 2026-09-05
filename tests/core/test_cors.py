from django.test import TestCase


class CorsPolicyTests(TestCase):
    def test_public_client_discovery_surfaces_have_open_credentialless_cors(self):
        for path in ("/api/v1/client-api/discovery/", "/.well-known/secondpass"):
            with self.subTest(path=path):
                response = self.client.get(
                    path,
                    HTTP_ORIGIN="http://evil.example",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.headers.get("Access-Control-Allow-Origin"),
                    "*",
                )
                self.assertNotEqual(
                    response.headers.get("Access-Control-Allow-Credentials"),
                    "true",
                )

    def test_browser_surfaces_are_not_cors_open(self):
        for path, statuses in (
            ("/login/", (200, 302)),
            ("/admin/", (200, 302, 404)),
            ("/", (200, 302)),
        ):
            with self.subTest(path=path):
                response = self.client.get(
                    path,
                    HTTP_ORIGIN="http://evil.example",
                )
                self.assertIn(response.status_code, statuses)
                self.assertIsNone(
                    response.headers.get("Access-Control-Allow-Origin")
                )

    def test_api_allows_idempotency_key_header_in_preflight(self):
        response = self.client.options(
            "/api/v1/marginalia/sessions/00000000-0000-0000-0000-000000000001/annotations/batch/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type, idempotency-key, authorization",
        )
        # CORS middleware should handle preflight for API paths.
        self.assertIn(response.status_code, (200, 204))
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        allow_headers = (response.headers.get("Access-Control-Allow-Headers") or "").lower()
        self.assertIn("idempotency-key", allow_headers)
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
