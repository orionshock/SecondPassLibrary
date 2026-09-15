from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
import zipfile

from django.test import SimpleTestCase

from library.imports.covers import extract_epub_cover
from library.imports.epub_metadata import read_import_metadata
from library.imports.epub_package import open_epub_package
from library.imports.errors import InvalidEpubImportError
from tests.library.imports.helpers import minimal_epub_bytes


class EpubPackageTests(SimpleTestCase):
    def test_discovers_the_first_supported_safe_rootfile(self):
        data = _epub_package(
            rootfiles="""
              <rootfile full-path="ignored.opf" media-type="application/not-opf"/>
              <rootfile full-path="OPS/books/content.opf"
                        media-type="application/oebps-package+xml"/>
            """,
            package_path="OPS/books/content.opf",
        )

        with open_epub_package(data) as package:
            self.assertEqual(package.package_path, "OPS/books/content.opf")
            self.assertEqual(package.read_package_document(), b"package")

    def test_rejects_missing_or_malformed_container_and_missing_package(self):
        cases = (
            _zip_bytes(("OPS/content.opf", b"package")),
            _zip_bytes(("META-INF/container.xml", b"<container")),
            _epub_package(rootfiles="", package_path="OPS/content.opf"),
            _epub_package(
                rootfiles='<rootfile full-path="OPS/missing.opf"/>',
                package_path=None,
            ),
        )

        for data in cases:
            with self.subTest(), self.assertRaises(InvalidEpubImportError):
                with open_epub_package(data):
                    pass

    def test_resolves_only_currently_supported_safe_package_references(self):
        data = _epub_package(
            rootfiles='<rootfile full-path="OPS/books/content.opf"/>',
            package_path="OPS/books/content.opf",
        )

        with open_epub_package(data) as package:
            self.assertEqual(
                package.resolve_package_reference("cover.png"),
                "OPS/books/cover.png",
            )
            self.assertEqual(
                package.resolve_package_reference("images/cover.png"),
                "OPS/books/images/cover.png",
            )
            self.assertEqual(
                package.resolve_package_reference(r"images\cover.png"),
                "OPS/books/images/cover.png",
            )
            for unsafe in (
                "../cover.png",
                "../../../cover.png",
                "/cover.png",
                "C:/cover.png",
                "https://example.test/cover.png",
                "bad\x00path.png",
                "",
            ):
                with self.subTest(unsafe=unsafe):
                    self.assertIsNone(package.resolve_package_reference(unsafe))

    def test_reads_members_with_the_callers_explicit_bound(self):
        data = _epub_package(
            rootfiles='<rootfile full-path="OPS/content.opf"/>',
            package_path="OPS/content.opf",
            extra_members=(("OPS/cover.bin", b"123456"),),
        )

        with open_epub_package(data) as package:
            self.assertEqual(
                package.read_member("OPS/cover.bin", max_bytes=6),
                b"123456",
            )
            with self.assertRaises(InvalidEpubImportError):
                package.read_member("OPS/cover.bin", max_bytes=5)

    def test_package_document_read_uses_its_existing_bound(self):
        data = _epub_package(
            rootfiles='<rootfile full-path="OPS/content.opf"/>',
            package_path="OPS/content.opf",
        )

        with (
            patch("library.imports.epub_package.MAX_PACKAGE_OPF_BYTES", 6),
            self.assertRaises(InvalidEpubImportError),
        ):
            with open_epub_package(data):
                pass

    def test_metadata_rejects_unsafe_rootfile_while_cover_remains_optional(self):
        data = _epub_package(
            rootfiles='<rootfile full-path="../content.opf"/>',
            package_path="content.opf",
        )

        with self.assertRaises(InvalidEpubImportError):
            read_import_metadata(data)
        self.assertIsNone(extract_epub_cover(data))

    def test_valid_metadata_caller_keeps_its_parsed_result(self):
        metadata = read_import_metadata(minimal_epub_bytes())

        self.assertEqual(metadata.title, "Sample EPUB")
        self.assertEqual(
            [author.name for author in metadata.authors], ["Sample Author"]
        )


def _epub_package(
    *,
    rootfiles: str,
    package_path: str | None,
    extra_members: tuple[tuple[str, bytes], ...] = (),
) -> bytes:
    container = f"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>{rootfiles}</rootfiles>
</container>
""".encode()
    members = [("META-INF/container.xml", container)]
    if package_path is not None:
        members.append((package_path, b"package"))
    members.extend(extra_members)
    return _zip_bytes(*members)


def _zip_bytes(*members: tuple[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return output.getvalue()
