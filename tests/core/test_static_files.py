from __future__ import annotations

import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.handlers.asgi import ASGIHandler
from django.test import (
    AsyncClient,
    AsyncRequestFactory,
    SimpleTestCase,
    override_settings,
)

from secondpass.settings import _staticfiles_backend


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"


class WhiteNoiseStaticFilesTests(SimpleTestCase):
    def test_response_adapter_wraps_standard_whitenoise_middleware(self):
        security_index = settings.MIDDLEWARE.index(
            "django.middleware.security.SecurityMiddleware"
        )
        adapter_index = settings.MIDDLEWARE.index(
            "core.asgi_streaming.asgi_streaming_response_middleware"
        )
        whitenoise_index = settings.MIDDLEWARE.index(
            "whitenoise.middleware.WhiteNoiseMiddleware"
        )

        self.assertEqual(adapter_index, security_index + 1)
        self.assertEqual(whitenoise_index, adapter_index + 1)

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
            assets = static_root / "product_ui" / "assets"
            assets.mkdir(parents=True)
            expected = {
                "app.js": (b'console.log("product ui");', 'text/javascript; charset="utf-8"'),
                "app.css": (b"body { color: black; }", 'text/css; charset="utf-8"'),
            }
            for name, (content, _content_type) in expected.items():
                (assets / name).write_bytes(content)

            with override_settings(
                DEBUG=False,
                STATIC_ROOT=static_root,
                WHITENOISE_AUTOREFRESH=False,
                MIDDLEWARE=[
                    "django.middleware.security.SecurityMiddleware",
                    "core.asgi_streaming.asgi_streaming_response_middleware",
                    "whitenoise.middleware.WhiteNoiseMiddleware",
                ],
            ):
                client = AsyncClient()
                for name, (expected_content, content_type) in expected.items():
                    with self.subTest(name=name):
                        response = await client.get(
                            f"/static/product_ui/assets/{name}"
                        )
                        with warnings.catch_warnings(record=True) as caught:
                            warnings.simplefilter("always")
                            try:
                                content = b"".join(
                                    [chunk async for chunk in response]
                                )
                            finally:
                                response.close()

                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.streaming)
                        self.assertTrue(response.is_async)
                        self.assertEqual(content, expected_content)
                        self.assertEqual(response["Content-Type"], content_type)
                        self.assertEqual(
                            response["Cache-Control"], "max-age=60, public"
                        )
                        self.assertFalse(
                            any(
                                "synchronous iterators" in str(item.message)
                                for item in caught
                            )
                        )

                        if name == "app.js":
                            handler = ASGIHandler()
                            handler.load_middleware(is_async=True)
                            request = AsyncRequestFactory().get(
                                f"/static/product_ui/assets/{name}",
                                headers={
                                    "if-modified-since": response["Last-Modified"]
                                },
                            )
                            conditional = await handler.get_response_async(request)
                            messages = []

                            async def send(message):
                                messages.append(message)

                            with warnings.catch_warnings(record=True) as caught:
                                warnings.simplefilter("always")
                                try:
                                    await handler.send_response(conditional, send)
                                    conditional_content = b"".join(
                                        message.get("body", b"")
                                        for message in messages
                                    )
                                finally:
                                    conditional.close()

                            self.assertEqual(conditional.status_code, 304)
                            self.assertEqual(conditional_content, b"")
                            self.assertEqual(
                                conditional["Cache-Control"],
                                response["Cache-Control"],
                            )
                            self.assertFalse(
                                any(
                                    "synchronous iterators" in str(item.message)
                                    for item in caught
                                )
                            )
