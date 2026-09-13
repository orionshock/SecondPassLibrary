from django.test import SimpleTestCase

from library.cover_objects import (
    SUPPORTED_COVER_EXTENSIONS,
    SUPPORTED_COVER_MEDIA_TYPES,
    canonical_cover_storage_name,
    cover_extension_for_image_format,
    is_canonical_cover_relative_path,
    is_canonical_cover_storage_name,
    is_immutable_public_cover_path,
)


class CanonicalCoverObjectTests(SimpleTestCase):
    def test_produced_name_is_canonical_for_storage_and_public_delivery(self):
        digest = "ab" * 32

        name = canonical_cover_storage_name(digest=digest, extension=".png")

        self.assertEqual(name, f"covers/ab/ab/{digest}.png")
        self.assertTrue(is_canonical_cover_storage_name(name))
        self.assertTrue(is_canonical_cover_relative_path(name.removeprefix("covers/")))
        self.assertTrue(is_immutable_public_cover_path(f"/media/{name}"))

    def test_canonical_recognition_rejects_malformed_or_unsupported_paths(self):
        digest = "ab" * 32
        paths = (
            f"aa/ab/{digest}.png",
            f"ab/ab/{digest[:-1]}.png",
            f"ab/ab/{digest}.gif",
            f"ab/ab/{'g' + digest[1:]}.png",
            f"ab/ab/{digest}.png/extra",
            "../books/private.epub",
            "default.png",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(is_canonical_cover_relative_path(path))
                self.assertFalse(
                    is_immutable_public_cover_path(f"/media/covers/{path}")
                )

    def test_supported_formats_have_one_extension_and_media_type_contract(self):
        self.assertEqual(SUPPORTED_COVER_EXTENSIONS, {".jpg", ".png", ".webp"})
        self.assertEqual(
            SUPPORTED_COVER_MEDIA_TYPES,
            {"image/jpeg", "image/png", "image/webp"},
        )
        self.assertEqual(cover_extension_for_image_format("JPEG"), ".jpg")
        self.assertEqual(cover_extension_for_image_format("PNG"), ".png")
        self.assertEqual(cover_extension_for_image_format("WEBP"), ".webp")
        self.assertIsNone(cover_extension_for_image_format("GIF"))
