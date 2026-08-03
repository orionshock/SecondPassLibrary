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

    def test_docker_build_collects_static_and_runtime_startup_does_not(self):
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("python manage.py collectstatic --noinput --clear", dockerfile)
        self.assertIn("/app/var/static/", dockerfile)
        self.assertNotIn("collectstatic", entrypoint)
