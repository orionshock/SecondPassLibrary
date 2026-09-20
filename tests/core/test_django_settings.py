from __future__ import annotations

import importlib
import os
from datetime import date, datetime, timezone
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.core.checks import Error, Tags, Warning, run_checks
from django.test import SimpleTestCase

from secondpass import version as version_module
from secondpass.settings import (
    INSECURE_FALLBACK_SECRET_KEY,
    PLACEHOLDER_SECRET_KEYS,
    _env_list,
    _secure_proxy_ssl_header,
    env,
)


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"


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
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_debug_defaults_off_and_hosts_are_local_safe_by_default(self):
        self.assertIs(settings.DEBUG, False)
        self.assertEqual(settings.ALLOWED_HOSTS[:3], ["localhost", "127.0.0.1", "[::1]"])
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_source_tree_version_uses_live_development_metadata(self):
        before_import = datetime.now(timezone.utc).date().isoformat()
        metadata = importlib.reload(version_module)
        after_import = datetime.now(timezone.utc).date().isoformat()

        self.assertEqual(metadata.SERVER_VERSION, "live-dev-env")
        self.assertEqual(
            date.fromisoformat(metadata.SERVER_RELEASE_DATE).isoformat(),
            metadata.SERVER_RELEASE_DATE,
        )
        self.assertIn(metadata.SERVER_RELEASE_DATE, {before_import, after_import})

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

    def test_library_urls_are_env_driven_without_changing_host_or_csrf_trust(self):
        env = os.environ | {
            "DJANGO_DEBUG": "1",
            "SECOND_PASS_LIBRARY_URLS": (
                "https://home.example/,https://public.example,https://HOME.example"
            ),
        }
        env.pop("DJANGO_ALLOWED_HOSTS", None)
        env.pop("DJANGO_CSRF_TRUSTED_ORIGINS", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from secondpass import settings; "
                "print(settings.SECOND_PASS_LIBRARY_URLS); "
                "print(settings.ALLOWED_HOSTS); "
                "print(settings.CSRF_TRUSTED_ORIGINS)",
            ],
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "['https://home.example', 'https://public.example']",
                "['localhost', '127.0.0.1', '[::1]']",
                "[]",
            ],
        )

    def test_malformed_library_url_rejects_settings_import(self):
        result = self._settings_import(
            {
                "DJANGO_DEBUG": "1",
                "SECOND_PASS_LIBRARY_URLS": "https://home.example/books",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECOND_PASS_LIBRARY_URLS", result.stderr)

    def test_silenced_system_checks_are_env_driven(self):
        self.assertEqual(settings.SILENCED_SYSTEM_CHECKS, [])
        with patch.dict(
            "os.environ",
            {"DJANGO_SILENCED_SYSTEM_CHECKS": "security.W004, security.W008"},
        ):
            self.assertEqual(
                _env_list("DJANGO_SILENCED_SYSTEM_CHECKS", []),
                ["security.W004", "security.W008"],
            )

    def test_django_admin_exposure_setting_is_env_driven_and_disabled_by_default(self):
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
        self.assertEqual(Path(settings.STATIC_ROOT), BACKEND_ROOT / "var" / "static")
        self.assertNotEqual(Path(settings.STATIC_ROOT).parent, settings.USERDATA_DIR)

    def test_product_ui_uses_the_canonical_backend_artifact_path(self):
        self.assertEqual(
            Path(settings.PRODUCT_UI_DIR), BACKEND_ROOT / "web" / "product_ui"
        )
        self.assertEqual(
            Path(settings.PRODUCT_UI_ASSETS_DIR),
            BACKEND_ROOT / "web" / "product_ui" / "assets",
        )

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

    def test_deploy_check_rejects_debug_mode(self):
        with self.settings(DEBUG=True):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        message = next(item for item in messages if item.id == "secondpass.E003")
        self.assertIsInstance(message, Error)
        self.assertTrue(message.hint)

    def test_deploy_check_rejects_wildcard_allowed_hosts_in_production(self):
        with self.settings(DEBUG=False, ALLOWED_HOSTS=["*"]):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        message = next(item for item in messages if item.id == "secondpass.E004")
        self.assertIsInstance(message, Error)
        self.assertTrue(message.hint)

    def test_deploy_check_rejects_empty_placeholder_and_malformed_hosts(self):
        cases = (
            ([], "secondpass.E005"),
            (["your-hostname-or-domain"], "secondpass.E006"),
            (["https://books.example.com"], "secondpass.E007"),
        )
        for allowed_hosts, expected_id in cases:
            with (
                self.subTest(allowed_hosts=allowed_hosts),
                self.settings(DEBUG=False, ALLOWED_HOSTS=allowed_hosts),
            ):
                messages = run_checks(
                    tags=[Tags.security],
                    include_deployment_checks=True,
                )

            message = next(item for item in messages if item.id == expected_id)
            self.assertIsInstance(message, Error)
            self.assertTrue(message.hint)

    def test_deploy_check_allows_local_and_internal_hosts(self):
        with self.settings(
            DEBUG=False,
            ALLOWED_HOSTS=["localhost", "127.0.0.1", "[::1]", "server"],
        ):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        ids = {message.id for message in messages}
        self.assertTrue(
            ids.isdisjoint(
                {
                    "secondpass.E004",
                    "secondpass.E005",
                    "secondpass.E006",
                    "secondpass.E007",
                }
            )
        )

    def test_deploy_check_rejects_trusted_https_proxy_without_secure_cookies(self):
        for session_secure, csrf_secure in (
            (False, False),
            (False, True),
            (True, False),
        ):
            with (
                self.subTest(session_secure=session_secure, csrf_secure=csrf_secure),
                self.settings(
                    DEBUG=False,
                    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
                    SESSION_COOKIE_SECURE=session_secure,
                    CSRF_COOKIE_SECURE=csrf_secure,
                ),
            ):
                messages = run_checks(
                    tags=[Tags.security],
                    include_deployment_checks=True,
                )

            self.assertIn("secondpass.E002", {message.id for message in messages})

    def test_deploy_check_allows_direct_local_http_with_insecure_cookies(self):
        with self.settings(
            DEBUG=False,
            SECURE_PROXY_SSL_HEADER=None,
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
        ):
            messages = run_checks(tags=[Tags.security], include_deployment_checks=True)

        self.assertNotIn("secondpass.E002", {message.id for message in messages})

    def test_deploy_check_accepts_trusted_https_proxy_with_secure_cookies(self):
        with self.settings(
            DEBUG=False,
            SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
            SESSION_COOKIE_SECURE=True,
            CSRF_COOKIE_SECURE=True,
        ):
            messages = run_checks(tags=[Tags.security], include_deployment_checks=True)

        self.assertNotIn("secondpass.E002", {message.id for message in messages})

    def test_trusted_proxy_check_rejects_malformed_missing_and_trust_all_entries(self):
        cases = (
            (["not-an-address"], False, "secondpass.E008"),
            ([], True, "secondpass.E009"),
            (["0.0.0.0/0"], True, "secondpass.E010"),
            (["::/0"], True, "secondpass.E010"),
            (["0.0.0.0/1", "128.0.0.0/1"], True, "secondpass.E010"),
        )
        for trusted_proxies, trust_forwarded_for, expected_id in cases:
            with (
                self.subTest(
                    trusted_proxies=trusted_proxies,
                    trust_forwarded_for=trust_forwarded_for,
                ),
                self.settings(
                    TRUSTED_PROXY_IPS=trusted_proxies,
                    TRUST_X_FORWARDED_FOR=trust_forwarded_for,
                ),
            ):
                messages = run_checks(tags=[Tags.security])

            message = next(item for item in messages if item.id == expected_id)
            self.assertIsInstance(message, Error)
            self.assertTrue(message.hint)

    def test_trusted_proxy_check_allows_exact_and_bounded_networks(self):
        with self.settings(
            TRUSTED_PROXY_IPS=["127.0.0.1", "10.20.0.0/16", "2001:db8::/64"],
            TRUST_X_FORWARDED_FOR=True,
        ):
            messages = run_checks(tags=[Tags.security])

        self.assertTrue(
            {message.id for message in messages}.isdisjoint(
                {"secondpass.E008", "secondpass.E009", "secondpass.E010"}
            )
        )

    def test_trusted_proxy_check_warns_for_duplicate_networks(self):
        with self.settings(
            TRUSTED_PROXY_IPS=["10.20.0.1", "10.20.0.1/32"],
            TRUST_X_FORWARDED_FOR=True,
        ):
            messages = run_checks(tags=[Tags.security])

        message = next(item for item in messages if item.id == "secondpass.W002")
        self.assertIsInstance(message, Warning)
        self.assertTrue(message.hint)

    def test_deploy_check_warns_for_forwarded_host_trust(self):
        with self.settings(
            DEBUG=False,
            ALLOWED_HOSTS=["books.example.com"],
            USE_X_FORWARDED_HOST=True,
        ):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        message = next(item for item in messages if item.id == "secondpass.W003")
        self.assertIsInstance(message, Warning)
        self.assertTrue(message.hint)

    def test_storage_check_rejects_static_media_path_overlap(self):
        root = ROOT / "test-storage-overlap"
        with self.settings(MEDIA_ROOT=root, STATIC_ROOT=root / "static"):
            messages = run_checks(tags=[Tags.security])

        message = next(item for item in messages if item.id == "secondpass.E011")
        self.assertIsInstance(message, Error)
        self.assertTrue(message.hint)

    def test_deploy_check_allows_proxy_owned_redirect_and_hsts(self):
        with self.settings(
            DEBUG=False,
            ALLOWED_HOSTS=["books.example.com"],
            SECURE_HSTS_SECONDS=0,
            SECURE_SSL_REDIRECT=False,
            SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
            SESSION_COOKIE_SECURE=True,
            CSRF_COOKIE_SECURE=True,
            USE_X_FORWARDED_HOST=False,
        ):
            messages = run_checks(
                tags=[Tags.security],
                include_deployment_checks=True,
            )

        self.assertFalse(
            [
                message
                for message in messages
                if message.id.startswith("secondpass.E")
            ]
        )
