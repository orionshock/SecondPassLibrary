from django.test import TestCase


class CorsDevOriginsTests(TestCase):
    def test_allowed_origin_gets_cors_header(self):
        response = self.client.get("/api/v1/health/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:5173",
        )

    def test_unlisted_origin_does_not_get_cors_header(self):
        response = self.client.get("/api/v1/health/", HTTP_ORIGIN="http://evil.example")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

