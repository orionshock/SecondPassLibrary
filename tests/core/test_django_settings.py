from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.core.checks import Tags, run_checks
from django.test import SimpleTestCase
import pytest

from secondpass.settings import (
    INSECURE_FALLBACK_SECRET_KEY,
    PLACEHOLDER_SECRET_KEYS,
    _env_list,
    _secure_proxy_ssl_header,
    env,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_pytest_django_db_smoke():
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


class DjangoSettingsContractTests(SimpleTestCase):
    def _settings_import(self, env_updates: dict[str, str | None]):
        env = os.environ.copy()
        for key, value in env_updates.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [sys.executable, "-c", "import secondpass.settings"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_debug_defaults_off_and_hosts_are_local_safe_by_default(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn('DEBUG = env.bool("DJANGO_DEBUG", default=False)', source)
        self.assertIn('ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS"', source)
        self.assertEqual(settings.ALLOWED_HOSTS[:3], ["localhost", "127.0.0.1", "[::1]"])
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_csv_env_parsing_handles_hosts_and_wildcard(self):
        with patch.dict(
            "os.environ",
            {"DJANGO_ALLOWED_HOSTS": "books.example.com, 192.168.1.25, my-server.local"},
        ):
            self.assertEqual(
                _env_list("DJANGO_ALLOWED_HOSTS", []),
                ["books.example.com", "192.168.1.25", "my-server.local"],
            )

        with patch.dict("os.environ", {"DJANGO_ALLOWED_HOSTS": "*"}):
            self.assertEqual(_env_list("DJANGO_ALLOWED_HOSTS", []), ["*"])

    def test_silenced_system_checks_are_env_driven(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn(
            'SILENCED_SYSTEM_CHECKS = _env_list("DJANGO_SILENCED_SYSTEM_CHECKS", [])',
            source,
        )
        with patch.dict(
            "os.environ",
            {"DJANGO_SILENCED_SYSTEM_CHECKS": "security.W004, security.W008"},
        ):
            self.assertEqual(
                _env_list("DJANGO_SILENCED_SYSTEM_CHECKS", []),
                ["security.W004", "security.W008"],
            )

    def test_django_admin_exposure_setting_is_env_driven_and_disabled_by_default(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn(
            'SECOND_PASS_ENABLE_DJANGO_ADMIN = env.bool(',
            source,
        )
        self.assertIn('"SECOND_PASS_ENABLE_DJANGO_ADMIN", default=False', source)
        self.assertIs(settings.SECOND_PASS_ENABLE_DJANGO_ADMIN, False)
        with patch.dict("os.environ", {"SECOND_PASS_ENABLE_DJANGO_ADMIN": "0"}):
            self.assertIs(env.bool("SECOND_PASS_ENABLE_DJANGO_ADMIN", default=True), False)
        with patch.dict("os.environ", {"SECOND_PASS_ENABLE_DJANGO_ADMIN": "1"}):
            self.assertIs(env.bool("SECOND_PASS_ENABLE_DJANGO_ADMIN", default=True), True)
        with patch.dict("os.environ", {"SECOND_PASS_ENABLE_DJANGO_ADMIN": "false"}):
            self.assertIs(env.bool("SECOND_PASS_ENABLE_DJANGO_ADMIN", default=True), False)
        with patch.dict("os.environ", {"SECOND_PASS_ENABLE_DJANGO_ADMIN": "true"}):
            self.assertIs(env.bool("SECOND_PASS_ENABLE_DJANGO_ADMIN", default=False), True)

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
                _env_list("DJANGO_CSRF_TRUSTED_ORIGINS", []),
                ["https://books.example.com", "http://192.168.1.25:8000"],
            )
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])

    def test_proxy_and_cookie_security_settings_are_env_driven(self):
        source = (ROOT / "secondpass" / "settings.py").read_text(encoding="utf-8")

        self.assertIn("SECURE_PROXY_SSL_HEADER = _secure_proxy_ssl_header()", source)
        self.assertIn(
            'USE_X_FORWARDED_HOST = env.bool("DJANGO_USE_X_FORWARDED_HOST", default=False)',
            source,
        )
        self.assertIn(
            '_SECURE_COOKIES = env.bool("DJANGO_SECURE_COOKIES", default=False)',
            source,
        )
        self.assertIsNone(getattr(settings, "SECURE_PROXY_SSL_HEADER", None))
        self.assertIs(settings.USE_X_FORWARDED_HOST, False)
        self.assertIs(settings.SESSION_COOKIE_SECURE, False)
        self.assertIs(settings.CSRF_COOKIE_SECURE, False)
        self.assertIs(env.bool("DJANGO_SECURE_COOKIES", default=False), False)

        with patch.dict("os.environ", {"DJANGO_TRUST_X_FORWARDED_PROTO": "1"}):
            self.assertEqual(
                _secure_proxy_ssl_header(),
                ("HTTP_X_FORWARDED_PROTO", "https"),
            )
        with patch.dict("os.environ", {"DJANGO_USE_X_FORWARDED_HOST": "1"}):
            self.assertIs(env.bool("DJANGO_USE_X_FORWARDED_HOST", default=False), True)
        with patch.dict("os.environ", {"DJANGO_SECURE_COOKIES": "1"}):
            self.assertIs(env.bool("DJANGO_SECURE_COOKIES", default=False), True)

    def test_static_root_is_generated_artifact_outside_userdata(self):
        self.assertEqual(Path(settings.STATIC_ROOT), ROOT / "var" / "static")
        self.assertNotEqual(Path(settings.STATIC_ROOT).parent, settings.USERDATA_DIR)

    def test_userdata_dir_supports_path_operations(self):
        self.assertEqual(Path(settings.USERDATA_DIR / "db"), Path(settings.USERDATA_DIR) / "db")

    def test_whitenoise_manifest_strictness_is_intentionally_relaxed(self):
        self.assertIs(settings.WHITENOISE_MANIFEST_STRICT, False)

    def test_cookie_samesite_and_httponly_contracts(self):
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertIs(settings.SESSION_COOKIE_HTTPONLY, True)
        self.assertIs(settings.CSRF_COOKIE_HTTPONLY, False)

    def test_drf_global_authentication_uses_session_auth_only(self):
        auth_classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]

        self.assertEqual(
            auth_classes,
            ["rest_framework.authentication.SessionAuthentication"],
        )
        self.assertNotIn("rest_framework.authentication.BasicAuthentication", auth_classes)

    def test_production_rejects_missing_secret_key(self):
        result = self._settings_import(
            {
                "DJANGO_DEBUG": "0",
                "DJANGO_SECRET_KEY": None,
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY must be set", result.stderr)

    def test_production_rejects_default_insecure_secret_key(self):
        result = self._settings_import(
            {
                "DJANGO_DEBUG": "0",
                "DJANGO_SECRET_KEY": INSECURE_FALLBACK_SECRET_KEY,
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY must be set", result.stderr)

    def test_production_rejects_documented_placeholder_secret_key(self):
        placeholder = next(iter(PLACEHOLDER_SECRET_KEYS))
        result = self._settings_import(
            {
                "DJANGO_DEBUG": "0",
                "DJANGO_SECRET_KEY": placeholder,
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY must be set", result.stderr)

    def test_production_accepts_explicit_secret_key(self):
        result = self._settings_import(
            {
                "DJANGO_DEBUG": "0",
                "DJANGO_SECRET_KEY": "test-explicit-production-secret-key",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_deploy_check_warns_for_wildcard_allowed_hosts_in_production(self):
        with self.settings(DEBUG=False, ALLOWED_HOSTS=["*"]):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        self.assertIn("secondpass.W001", {message.id for message in messages})

    def test_deploy_check_warns_for_trusted_proxy_without_secure_cookies(self):
        with self.settings(
            DEBUG=False,
            SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
        ):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        self.assertIn("secondpass.W002", {message.id for message in messages})
