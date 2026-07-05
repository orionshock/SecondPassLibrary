from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
import zipfile

from accounts.models import UserProfile
from library.models import Book
from tests.library.imports.helpers import (
    BaseImportApiTest,
    epub_with_embedded_cover_bytes,
    mock_epub,
    png_bytes,
)
from tests.utils.responses import payload_list, response_data_dict, assert_response


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiZipUploadTests(BaseImportApiTest):
    @patch("library.imports.epub.epub.read_epub")
    def test_authenticated_can_upload_zip_with_multiple_epubs_ignores_non_epub_and_path_traversal(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"bytes-a")
            zf.writestr("notes.txt", b"ignore")
            zf.writestr("../evil.epub", b"nope")
            zf.writestr("nested/b.epub", b"bytes-b")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["source_type"], "zip")
        self.assertEqual(data["total_found"], 2)
        items = payload_list(data, "items")
        self.assertEqual(len(items), 2)
        self.assertTrue(
            all(item["status"] in {"imported", "duplicate", "failed"} for item in items)
        )

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_member_dot_segment_is_normalized_for_sidecar_matching(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Dot Segment OPF Title</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.png" media-type="image/png"/>
  </manifest>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Some ZIP tools include harmless "./" segments; importer should normalize these.
            zf.writestr("dir/./Book.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", opf_xml)
            zf.writestr("dir/cover.png", png_bytes())
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 1)

        book = Book.objects.get(title="Dot Segment OPF Title")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "opf_sidecar")

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_member_normalization_collision_is_skipped_safely(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # These normalize to the same member name.
            zf.writestr("dir/book.epub", b"bytes-a")
            zf.writestr("dir/./book.epub", b"bytes-b")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        # Ambiguous/unsafe normalized paths are skipped (no items created).
        self.assertEqual(data["total_found"], 0)
        self.assertEqual(len(payload_list(data, "items")), 0)

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_metadata_opf_precedence_and_cover(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Title</dc:title>
    <dc:creator>OPF Author</dc:creator>
    <dc:publisher>OPF Pub</dc:publisher>
    <dc:language>en</dc:language>
    <dc:subject>Fantasy</dc:subject>
    <dc:description>OPF Summary</dc:description>
    <meta name="calibre:series" content="Dresden Files"/>
    <meta name="calibre:series_index" content="3"/>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.png" media-type="image/png"/>
  </manifest>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "CalibreLibrary/Jim Butcher/Academ's Fury (126)/Academ's Fury - Jim Butcher.epub",
                b"epub-bytes",
            )
            zf.writestr(
                "CalibreLibrary/Jim Butcher/Academ's Fury (126)/metadata.opf", opf_xml
            )
            zf.writestr(
                "CalibreLibrary/Jim Butcher/Academ's Fury (126)/cover.png", png_bytes()
            )
        buf.seek(0)

        upload = SimpleUploadedFile(
            "calibre.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        book = Book.objects.get(title="OPF Title")
        self.assertEqual(book.publisher, "OPF Pub")
        self.assertEqual(book.summary, "OPF Summary")
        self.assertEqual(book.language, "en")
        self.assertIn("Fantasy", book.subjects or [])
        self.assertIsNotNone(book.series)
        assert book.series is not None
        self.assertEqual(book.series.name, "Dresden Files")
        self.assertEqual(str(book.series_index), "3.0")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "opf_sidecar")

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_order_prefers_metadata_opf(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        meta_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Meta OPF Title</dc:title>
</metadata></package>
"""
        base_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Basename OPF Title</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Foo.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", meta_opf)
            zf.writestr("dir/Foo.opf", base_opf)
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Meta OPF Title").exists())
        self.assertFalse(Book.objects.filter(title="Basename OPF Title").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_same_basename_fallback(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        base_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Basename Only</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Foo.epub", b"epub-bytes")
            zf.writestr("dir/Foo.opf", base_opf)
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Basename Only").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_unique_opf_fallback(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        lone_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Only OPF</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Book.epub", b"epub-bytes")
            zf.writestr("dir/random.opf", lone_opf)
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Only OPF").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_cover_invalid_falls_back_to_embedded_epub_cover(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Title 2</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.svg" media-type="image/svg+xml"/>
  </manifest>
</package>
"""

        epub_bytes = epub_with_embedded_cover_bytes(cover_size=(9, 10))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/book.epub", epub_bytes)
            zf.writestr("dir/metadata.opf", opf_xml)
            zf.writestr(
                "dir/cover.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
            )
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        book = Book.objects.get(title="OPF Title 2")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "epub")
        self.assertEqual(book.cover_width, 9)
        self.assertEqual(book.cover_height, 10)

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_security_bad_href_and_malformed_or_too_big_opf_ignored(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        bad_href_opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Bad Href</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="../cover.png" media-type="image/png"/>
  </manifest>
</package>
"""
        malformed_opf = "<package><metadata"  # invalid XML
        too_big = ("x" * (1024 * 1024 + 10)).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a/book.epub", b"epub-bytes-a")
            zf.writestr("a/metadata.opf", bad_href_opf)
            zf.writestr("a/cover.png", png_bytes())

            zf.writestr("b/book.epub", b"epub-bytes-b")
            zf.writestr("b/metadata.opf", malformed_opf)

            zf.writestr("c/book.epub", b"epub-bytes-c")
            zf.writestr("c/metadata.opf", too_big)
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        b1 = Book.objects.get(title="OPF Bad Href")
        self.assertFalse(bool(b1.cover_file))

        # Malformed/too-big OPFs should fall back to EPUB metadata from mock_epub.
        self.assertTrue(Book.objects.filter(title="Test Title").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_opf_with_doctype_entity_is_ignored_safely(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self._login_librarian()

        unsafe_opf = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE package [
  <!ENTITY unsafe "Unsafe OPF Title">
]>
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>&unsafe;</dc:title>
  </metadata>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/book.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", unsafe_opf)
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Book.objects.filter(title="Unsafe OPF Title").exists())
        self.assertTrue(Book.objects.filter(title="Test Title").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_duplicate_epub_does_not_refresh_metadata_from_sidecar_opf(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        opf1 = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>First Title</dc:title>
</metadata></package>
"""
        opf2 = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Second Title</dc:title>
</metadata></package>
"""

        def upload_zip(opf_xml: str):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("dir/book.epub", b"dup-bytes")
                zf.writestr("dir/metadata.opf", opf_xml)
            buf.seek(0)
            upload = SimpleUploadedFile(
                "bundle.zip", buf.read(), content_type="application/zip"
            )
            return assert_response(
                self.client.post(
                    "/api/v1/library/imports/",
                    data={"file": upload},
                    format="multipart",
                )
            )

        r1 = upload_zip(opf1)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="First Title").exists())

        r2 = upload_zip(opf2)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        data2 = response_data_dict(r2)
        self.assertEqual(data2["duplicate_count"], 1)
        self.assertTrue(Book.objects.filter(title="First Title").exists())
        self.assertFalse(Book.objects.filter(title="Second Title").exists())
