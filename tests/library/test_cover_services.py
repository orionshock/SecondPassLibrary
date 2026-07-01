from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.test import TestCase

from PIL import Image

from library.cover_services import (
    MAX_COVER_BYTES,
    MAX_COVER_DIMENSION,
    set_book_cover_from_bytes,
    validate_cover_image_bytes,
)
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


def _image_bytes(*, fmt: str, size: tuple[int, int] = (64, 80)) -> bytes:
    img = Image.new("RGB", size, color=(12, 34, 56))
    bio = BytesIO()
    img.save(bio, format=fmt)
    return bio.getvalue()


class CoverValidationTests(TestCase):
    def test_accepts_jpeg(self):
        info = validate_cover_image_bytes(data=_image_bytes(fmt="JPEG"))
        self.assertEqual(info.mime, "image/jpeg")
        self.assertEqual(info.extension, ".jpg")
        self.assertGreater(info.width, 0)
        self.assertGreater(info.height, 0)

    def test_accepts_png(self):
        info = validate_cover_image_bytes(data=_image_bytes(fmt="PNG"))
        self.assertEqual(info.mime, "image/png")
        self.assertEqual(info.extension, ".png")

    def test_accepts_webp(self):
        info = validate_cover_image_bytes(data=_image_bytes(fmt="WEBP"))
        self.assertEqual(info.mime, "image/webp")
        self.assertEqual(info.extension, ".webp")

    def test_rejects_svg(self):
        with self.assertRaises(ValueError):
            validate_cover_image_bytes(data=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")

    def test_rejects_gif(self):
        with self.assertRaises(ValueError):
            validate_cover_image_bytes(data=_image_bytes(fmt="GIF"))

    def test_rejects_corrupt_bytes(self):
        with self.assertRaises(ValueError):
            validate_cover_image_bytes(data=b"not an image")

    def test_rejects_oversized_bytes(self):
        with self.assertRaises(ValueError):
            validate_cover_image_bytes(data=b"x" * (MAX_COVER_BYTES + 1))

    def test_rejects_absurd_dimensions(self):
        too_wide = MAX_COVER_DIMENSION + 1
        data = _image_bytes(fmt="PNG", size=(too_wide, 10))
        with self.assertRaises(ValueError):
            validate_cover_image_bytes(data=data)

    def test_rejects_pillow_decompression_bomb_error(self):
        bomb_error = getattr(Image, "DecompressionBombError", None)
        if bomb_error is None:
            self.skipTest("Pillow does not expose DecompressionBombError")

        with patch("library.cover_services.Image.open", side_effect=bomb_error("bomb")):
            with self.assertRaises(ValueError):
                validate_cover_image_bytes(data=b"x" * 32)


class CoverStorageTests(IsolatedMediaRootMixin, TestCase):
    def test_sets_book_cover_and_metadata_and_path(self):
        book = create_file_backed_book(title="Has Cover").book
        data = _image_bytes(fmt="PNG", size=(40, 50))
        info = set_book_cover_from_bytes(book=book, data=data, source="manual")

        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "manual")
        self.assertEqual(book.cover_mime, "image/png")
        self.assertEqual(book.cover_width, 40)
        self.assertEqual(book.cover_height, 50)

        # Content-addressed-ish storage: covers/<first2>/<next2>/<sha>.<ext>
        expected_prefix = f"covers/{info.sha256[:2]}/{info.sha256[2:4]}/{info.sha256}"
        cover_name = book.cover_file.name
        assert cover_name is not None
        self.assertTrue(cover_name.startswith(expected_prefix))
        self.assertTrue(cover_name.endswith(".png"))
