from __future__ import annotations

import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import AsyncRequestFactory, SimpleTestCase, override_settings

from core.asgi_streaming import AsyncWhiteNoiseMiddleware
from secondpass.settings import _staticfiles_backend


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"


class WhiteNoiseStaticFilesTests(SimpleTestCase):
    def test_whitenoise_middleware_follows_security_middleware(self):
        security_index = settings.MIDDLEWARE.index(
            "django.middleware.security.SecurityMiddleware"
        )
        whitenoise_index = settings.MIDDLEWARE.index(
            "core.asgi_streaming.AsyncWhiteNoiseMiddleware"
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

    async def test_whitenoise_asset_streams_without_sync_iterator_adaptation(self):
        with TemporaryDirectory() as directory:
            static_root = Path(directory)
            asset = static_root / "product_ui" / "assets" / "app.js"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'console.log("product ui");')

            with override_settings(
                DEBUG=False,
                STATIC_ROOT=static_root,
                WHITENOISE_AUTOREFRESH=False,
            ):
                middleware = AsyncWhiteNoiseMiddleware(lambda request: None)
                request = AsyncRequestFactory().get(
                    "/static/product_ui/assets/app.js"
                )
                response = middleware(request)

                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        content = b"".join([chunk async for chunk in response])
                    finally:
                        response.close()

        self.assertTrue(response.streaming)
        self.assertTrue(response.is_async)
        self.assertEqual(content, b'console.log("product ui");')
        self.assertEqual(response["Content-Type"], 'text/javascript; charset="utf-8"')
        self.assertEqual(response["Cache-Control"], "max-age=60, public")
        self.assertFalse(
            any("synchronous iterators" in str(item.message) for item in caught)
        )
