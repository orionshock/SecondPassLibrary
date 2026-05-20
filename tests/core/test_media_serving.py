from __future__ import annotations

import os
from pathlib import Path
import uuid
from io import BytesIO
from typing import Any, cast

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
import django.core.files.storage as storage
from django.utils.functional import empty

from PIL import Image

from library.cover_services import set_book_cover_from_bytes
from library.models import Book


class DebugMediaServingSmokeTest(TestCase):
    def setUp(self):
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        self._media_root = str(temp_root / f"tmp_media_serve_{uuid.uuid4().hex}")
        os.makedirs(self._media_root, exist_ok=True)

        self._override = override_settings(DEBUG=True, MEDIA_ROOT=self._media_root)
        self._override.enable()

        handler = cast(Any, getattr(storage, "storages"))
        handler._storages = {}
        handler._backends = None
        setattr(cast(Any, storage.default_storage), "_wrapped", empty)

    def tearDown(self):
        self._override.disable()
        __import__("shutil").rmtree(self._media_root, ignore_errors=True)

    def _png_bytes(self) -> bytes:
        img = Image.new("RGB", (10, 12), color=(1, 2, 3))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_debug_django_serves_media_url_for_cover_file(self):
        # This tests the development convenience route that serves MEDIA_ROOT at
        # MEDIA_URL via Django only when DEBUG=True. It does not imply MEDIA_URL
        # is debug-only; production deployments should serve MEDIA_ROOT at
        # MEDIA_URL outside Django.
        book = Book.objects.create(title="Has Cover")
        set_book_cover_from_bytes(book=book, data=self._png_bytes(), source="manual")
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))

        url = book.cover_file.url
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
