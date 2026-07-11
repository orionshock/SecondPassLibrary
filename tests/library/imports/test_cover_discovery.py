from __future__ import annotations

from io import BytesIO
from unittest import skipUnless

from django.test import TestCase
from PIL import features

from library.imports.epub import import_epub_file
from library.imports.results import IMPORT_STATUS_IMPORTED
from tests.library.imports.helpers import epub_with_cover_bytes, image_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class EpubCoverDiscoveryTests(IsolatedMediaRootMixin, TestCase):
    def test_epub3_manifest_cover_image_is_saved(self):
        result = import_epub_file(
            BytesIO(epub_with_cover_bytes(cover_bytes=image_bytes("PNG"))),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".png"))

    def test_epub2_meta_cover_is_saved(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("JPEG"),
                    cover_href="images/cover.jpg",
                    media_type="image/jpeg",
                    properties="",
                    epub2_meta=True,
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".jpg"))

    def test_jpeg_cover_is_accepted(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("JPEG"),
                    cover_href="images/cover.jpg",
                    media_type="image/jpeg",
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".jpg"))

    def test_png_cover_is_accepted(self):
        result = import_epub_file(
            BytesIO(epub_with_cover_bytes(cover_bytes=image_bytes("PNG"))),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".png"))

    @skipUnless(features.check("webp"), "Pillow WebP support is unavailable.")
    def test_webp_cover_is_accepted_when_supported(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("WEBP"),
                    cover_href="images/cover.webp",
                    media_type="image/webp",
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".webp"))
