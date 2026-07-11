from __future__ import annotations

from io import BytesIO
from unittest import skipUnless
import zipfile

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

    def test_nested_opf_directory_relative_cover_path_is_saved(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("PNG"),
                    opf_path="OPS/books/content.opf",
                    cover_href="assets/cover.png",
                )
            ),
            source_filename="nested-cover.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".png"))

    def test_content_type_wins_over_extension_and_manifest_media_type(self):
        result = import_epub_file(
            BytesIO(
                epub_with_cover_bytes(
                    cover_bytes=image_bytes("PNG"),
                    cover_href="images/cover.jpg",
                    media_type="image/jpeg",
                )
            ),
            source_filename="mismatch.epub",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.book.cover_file.name.endswith(".png"))

    def test_epub3_cover_image_wins_before_epub2_meta_cover(self):
        result = import_epub_file(
            BytesIO(_epub_with_epub3_and_epub2_covers()),
            source_filename="competing-covers.epub",
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


def _epub_with_epub3_and_epub2_covers() -> bytes:
    opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:opf="http://www.idpf.org/2007/opf"
         unique-identifier="BookId"
         version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Competing Covers</dc:title>
    <dc:creator>Cover Author</dc:creator>
    <dc:language>en</dc:language>
    <meta name="cover" content="epub2-cover"/>
  </metadata>
  <manifest>
    <item id="epub3-cover" href="images/epub3.png" media-type="image/png" properties="cover-image"/>
    <item id="epub2-cover" href="images/epub2.jpg" media-type="image/jpeg"/>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter"/>
  </spine>
</package>
"""
    container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf_xml)
        zf.writestr("OEBPS/chapter.xhtml", "<html xmlns='http://www.w3.org/1999/xhtml'><body/></html>")
        zf.writestr("OEBPS/images/epub3.png", image_bytes("PNG"))
        zf.writestr("OEBPS/images/epub2.jpg", image_bytes("JPEG"))
    return out.getvalue()
