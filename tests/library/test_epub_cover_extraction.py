from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
import uuid
import zipfile
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase

from PIL import Image

from library.epub_services import ImportStatus
from library.models import BookFile
from library.services import import_epub

from tests.library.utils import IsolatedMediaRootMixin


def _png_bytes(*, size: tuple[int, int] = (40, 60)) -> bytes:
    img = Image.new("RGB", size, color=(7, 8, 9))
    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _write_epub_zip(
    *,
    out_path: str,
    opf_path: str,
    opf_xml: str,
    cover_member: str | None = None,
    cover_bytes: bytes | None = None,
) -> None:
    container_xml = f"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_xml)
        if cover_member and cover_bytes is not None:
            zf.writestr(cover_member, cover_bytes)


class EmbeddedEpubCoverExtractionTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(temp_root / f"tmp_epub_cover_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=True)

    def tearDown(self):
        __import__("shutil").rmtree(self.temp_dir, ignore_errors=True)

    @patch("library.services.epub.read_epub")
    def test_epub3_cover_image_properties_extracted(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "book.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="images/cover.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
        _write_epub_zip(
            out_path=epub_path,
            opf_path=opf_path,
            opf_xml=opf_xml,
            cover_member="OEBPS/images/cover.png",
            cover_bytes=_png_bytes(),
        )

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "epub")
        self.assertEqual(book.cover_mime, "image/png")
        self.assertEqual(book.cover_width, 40)
        self.assertEqual(book.cover_height, 60)

    @patch("library.services.epub.read_epub")
    def test_epub2_meta_cover_id_extracted(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "book2.epub")
        opf_path = "OPS/package.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.png" media-type="image/png"/>
  </manifest>
</package>
"""
        _write_epub_zip(
            out_path=epub_path,
            opf_path=opf_path,
            opf_xml=opf_xml,
            cover_member="OPS/cover.png",
            cover_bytes=_png_bytes(size=(22, 33)),
        )

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "epub")
        self.assertEqual(book.cover_width, 22)
        self.assertEqual(book.cover_height, 33)

    @patch("library.services.epub.read_epub")
    def test_no_cover_imports_successfully(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "nocover.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest></manifest>
</package>
"""
        _write_epub_zip(out_path=epub_path, opf_path=opf_path, opf_xml=opf_xml)

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertFalse(bool(book.cover_file))

    @patch("library.services.epub.read_epub")
    def test_path_traversal_cover_href_is_ignored(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "traversal.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="../secret.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
        _write_epub_zip(out_path=epub_path, opf_path=opf_path, opf_xml=opf_xml, cover_member="secret.png", cover_bytes=_png_bytes())

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertFalse(bool(book.cover_file))

    @patch("library.services.epub.read_epub")
    def test_url_like_cover_href_is_ignored(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "urlhref.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="https://example.com/cover.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
        _write_epub_zip(out_path=epub_path, opf_path=opf_path, opf_xml=opf_xml)

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertFalse(bool(book.cover_file))

    @patch("library.services.epub.read_epub")
    def test_svg_cover_is_rejected_and_import_succeeds(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        epub_path = os.path.join(self.temp_dir, "svg.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="images/cover.svg" media-type="image/svg+xml" properties="cover-image"/>
  </manifest>
</package>
"""
        _write_epub_zip(
            out_path=epub_path,
            opf_path=opf_path,
            opf_xml=opf_xml,
            cover_member="OEBPS/images/cover.svg",
            cover_bytes=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        )

        result = import_epub(epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None
        book.refresh_from_db()
        self.assertFalse(bool(book.cover_file))

    @patch("library.services.epub.read_epub")
    def test_duplicate_epub_does_not_replace_existing_cover(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        # First import with a cover.
        epub_path = os.path.join(self.temp_dir, "dup.epub")
        opf_path = "OEBPS/content.opf"
        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="images/cover.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
        _write_epub_zip(
            out_path=epub_path,
            opf_path=opf_path,
            opf_xml=opf_xml,
            cover_member="OEBPS/images/cover.png",
            cover_bytes=_png_bytes(size=(11, 12)),
        )
        r1 = import_epub(epub_path)
        self.assertEqual(r1.status, ImportStatus.IMPORTED)
        book1 = r1.book
        assert book1 is not None
        book1.refresh_from_db()
        first_cover_name = book1.cover_file.name
        self.assertTrue(first_cover_name)

        # Second import of the same file should be detected as duplicate and not modify cover.
        r2 = import_epub(epub_path)
        self.assertEqual(r2.status, ImportStatus.DUPLICATE)
        existing_file = BookFile.objects.get(checksum=r2.checksum)
        existing_file.book.refresh_from_db()
        self.assertEqual(existing_file.book.cover_file.name, first_cover_name)
