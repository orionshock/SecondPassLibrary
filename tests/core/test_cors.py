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
        self.assertIn(response.status_code, (200, 302))
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
