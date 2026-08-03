from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from secondpass.settings import _staticfiles_backend


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"


class WhiteNoiseStaticFilesTests(SimpleTestCase):
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
        self.assertEqual(Path(settings.STATIC_ROOT), BACKEND_ROOT / "var" / "static")
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
