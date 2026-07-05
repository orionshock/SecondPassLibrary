from django.test import TestCase


class CorsPolicyTests(TestCase):
    def test_api_discovery_has_open_cors(self):
        response = self.client.get(
            "/api/v1/client-api/discovery/",
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_well_known_has_open_cors(self):
        response = self.client.get(
            "/.well-known/secondpass",
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_product_ui_authorize_is_not_cors_open(self):
        response = self.client.get(
            "/client-api/authorize/",
            HTTP_ORIGIN="http://evil.example",
        )
        # Redirect to login is fine; but it must not be CORS-open.
        self.assertIn(response.status_code, (200, 302))
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_admin_is_not_cors_open(self):
        response = self.client.get(
            "/admin/",
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertIn(response.status_code, (200, 302, 404))
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_product_ui_dashboard_is_not_cors_open(self):
        response = self.client.get(
            "/dashboard/",
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_api_allows_idempotency_key_header_in_preflight(self):
        response = self.client.options(
            "/api/v1/reading/annotations/",
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
