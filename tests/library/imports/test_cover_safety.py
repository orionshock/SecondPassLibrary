from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.test import TestCase

from library.imports.covers import extract_epub_cover, validate_cover_bytes
from library.imports.epub import import_epub_file
from library.imports.results import IMPORT_STATUS_IMPORTED
from tests.library.imports.helpers import epub_with_cover_bytes, image_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class EpubCoverSafetyTests(IsolatedMediaRootMixin, TestCase):
    def test_shared_cover_byte_validator_accepts_supported_formats(self):
        expected = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

        for image_format, extension in expected.items():
            with self.subTest(image_format=image_format):
                cover = validate_cover_bytes(image_bytes(image_format))
                self.assertIsNotNone(cover)
                self.assertEqual(cover.extension, extension)

    def test_shared_cover_byte_validator_rejects_unsupported_image_format(self):
        self.assertIsNone(validate_cover_bytes(image_bytes("GIF")))

    def test_svg_cover_is_ignored_and_import_still_succeeds(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                    cover_href="images/cover.svg",
                    media_type="image/svg+xml",
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.book.cover_file.name, "")

    def test_corrupt_cover_is_ignored_and_import_still_succeeds(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=b"not an image",
                    cover_href="images/cover.jpg",
                    media_type="image/jpeg",
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.book.cover_file.name, "")

    def test_unsafe_traversal_cover_href_is_ignored(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("PNG"),
                    cover_href="../cover.png",
                    cover_member_name="cover.png",
                )
            ),
            source_filename="cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.book.cover_file.name, "")

    def test_backslash_traversal_cover_href_is_rejected_by_extractor(self):
        cover = extract_epub_cover(
            epub_with_cover_bytes(
                cover_bytes=image_bytes("PNG"),
                cover_href=r"..\cover.png",
                cover_member_name="cover.png",
            )
        )

        self.assertIsNone(cover)

    def test_absolute_cover_href_is_rejected_by_extractor(self):
        cover = extract_epub_cover(
            epub_with_cover_bytes(
                cover_bytes=image_bytes("PNG"),
                cover_href="/cover.png",
                cover_member_name="cover.png",
            )
        )

        self.assertIsNone(cover)

    def test_windows_drive_cover_href_is_rejected_by_extractor(self):
        cover = extract_epub_cover(
            epub_with_cover_bytes(
                cover_bytes=image_bytes("PNG"),
                cover_href="C:/cover.png",
                cover_member_name="OEBPS/images/cover.png",
            )
        )

        self.assertIsNone(cover)

    def test_url_like_cover_href_is_rejected_by_extractor(self):
        cover = extract_epub_cover(
            epub_with_cover_bytes(
                cover_bytes=image_bytes("PNG"),
                cover_href="https://example.test/cover.png",
                cover_member_name="OEBPS/images/cover.png",
            )
        )

        self.assertIsNone(cover)

    def test_too_many_cover_pixels_is_ignored(self):
        with patch("library.imports.covers.MAX_COVER_IMAGE_PIXELS", 1):
            result = import_epub_file(
                BytesIO(epub_with_cover_bytes(cover_bytes=image_bytes("PNG"))),
                source_filename="cover.epub",
            )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.book.cover_file.name, "")

    def test_oversized_cover_is_ignored(self):
        with patch("library.imports.covers.MAX_COVER_IMAGE_BYTES", 1):
            result = import_epub_file(
                BytesIO(epub_with_cover_bytes(cover_bytes=image_bytes("PNG"))),
                source_filename="cover.epub",
            )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.book.cover_file.name, "")
