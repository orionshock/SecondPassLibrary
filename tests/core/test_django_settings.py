from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from secondpass.settings import _env_bool, _env_csv, _secure_proxy_ssl_header


ROOT = Path(__file__).resolve().parents[2]


class DjangoSettingsContractTests(SimpleTestCase):
    def test_debug_defaults_off_and_hosts_are_local_safe_by_default(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn('DEBUG = _env_bool("DJANGO_DEBUG", False)', source)
        self.assertIn('ALLOWED_HOSTS = _env_csv("DJANGO_ALLOWED_HOSTS"', source)
        self.assertEqual(settings.ALLOWED_HOSTS[:3], ["localhost", "127.0.0.1", "[::1]"])
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_csv_env_parsing_handles_hosts_and_wildcard(self):
        with patch.dict(
            "os.environ",
            {"DJANGO_ALLOWED_HOSTS": "books.example.com, 192.168.1.25, my-server.local"},
        ):
            self.assertEqual(
                _env_csv("DJANGO_ALLOWED_HOSTS", []),
                ["books.example.com", "192.168.1.25", "my-server.local"],
            )

        with patch.dict("os.environ", {"DJANGO_ALLOWED_HOSTS": "*"}):
            self.assertEqual(_env_csv("DJANGO_ALLOWED_HOSTS", []), ["*"])

    def test_csrf_trusted_origins_are_env_driven(self):
        with patch.dict(
            "os.environ",
            {
                "DJANGO_CSRF_TRUSTED_ORIGINS": (
                    "https://books.example.com, http://192.168.1.25:8000"
                )
            },
        ):
            self.assertEqual(
                _env_csv("DJANGO_CSRF_TRUSTED_ORIGINS", []),
                ["https://books.example.com", "http://192.168.1.25:8000"],
            )
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])

    def test_proxy_and_cookie_security_settings_are_env_driven(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn("SECURE_PROXY_SSL_HEADER = _secure_proxy_ssl_header()", source)
        self.assertIn(
            'USE_X_FORWARDED_HOST = _env_bool("DJANGO_USE_X_FORWARDED_HOST", False)',
            source,
        )
        self.assertIn(
            '_SECURE_COOKIES = _env_bool("DJANGO_SECURE_COOKIES", False)',
            source,
        )
        self.assertIsNone(getattr(settings, "SECURE_PROXY_SSL_HEADER", None))
        self.assertIs(settings.USE_X_FORWARDED_HOST, False)
        self.assertIs(settings.SESSION_COOKIE_SECURE, False)
        self.assertIs(settings.CSRF_COOKIE_SECURE, False)
        self.assertIs(_env_bool("DJANGO_SECURE_COOKIES", False), False)

        with patch.dict("os.environ", {"DJANGO_TRUST_X_FORWARDED_PROTO": "1"}):
            self.assertEqual(
                _secure_proxy_ssl_header(),
                ("HTTP_X_FORWARDED_PROTO", "https"),
            )
        with patch.dict("os.environ", {"DJANGO_USE_X_FORWARDED_HOST": "1"}):
            self.assertIs(_env_bool("DJANGO_USE_X_FORWARDED_HOST", False), True)
        with patch.dict("os.environ", {"DJANGO_SECURE_COOKIES": "1"}):
            self.assertIs(_env_bool("DJANGO_SECURE_COOKIES", False), True)

    def test_static_root_is_generated_artifact_outside_userdata(self):
        self.assertEqual(Path(settings.STATIC_ROOT), ROOT / "var" / "static")
        self.assertNotEqual(Path(settings.STATIC_ROOT).parent, settings.USERDATA_DIR)

    def test_whitenoise_manifest_strictness_is_intentionally_relaxed(self):
        self.assertIs(settings.WHITENOISE_MANIFEST_STRICT, False)

    def test_cookie_samesite_and_httponly_contracts(self):
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertIs(settings.SESSION_COOKIE_HTTPONLY, True)
        self.assertIs(settings.CSRF_COOKIE_HTTPONLY, False)
