from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from secondpass.settings import _staticfiles_backend


ROOT = Path(__file__).resolve().parents[2]


class WhiteNoiseStaticFilesTests(SimpleTestCase):
    def test_whitenoise_dependency_is_declared(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("whitenoise==", requirements)

    def test_whitenoise_middleware_follows_security_middleware(self):
        security_index = settings.MIDDLEWARE.index(
            "django.middleware.security.SecurityMiddleware"
        )
        whitenoise_index = settings.MIDDLEWARE.index(
            "whitenoise.middleware.WhiteNoiseMiddleware"
        )

        self.assertEqual(whitenoise_index, security_index + 1)

    def test_static_root_and_production_whitenoise_storage_are_configured(self):
        self.assertTrue(settings.STATIC_ROOT)
        self.assertEqual(Path(settings.STATIC_ROOT), ROOT / "var" / "static")
        self.assertFalse(Path(settings.STATIC_ROOT).is_relative_to(ROOT / "userdata"))
        self.assertEqual(settings.STATIC_URL, "/static/")
        self.assertEqual(
            _staticfiles_backend(debug=False),
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(
            _staticfiles_backend(debug=True),
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )

    def test_production_startup_collects_static_before_asgi_server(self):
        script_servers = {
            "scripts/start-local-production.ps1": "-m uvicorn",
            "docker/entrypoint.sh": "python -m uvicorn secondpass.asgi:application",
        }
        for script_name, server_marker in script_servers.items():
            with self.subTest(script_name=script_name):
                source = (ROOT / script_name).read_text(
                    encoding="utf-8"
                )

                self.assertLess(
                    source.index("manage.py collectstatic --noinput"),
                    source.index(server_marker),
                )
