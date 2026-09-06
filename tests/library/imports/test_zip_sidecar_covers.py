from __future__ import annotations

from pathlib import Path
import zipfile
from unittest.mock import patch

from django.test import TestCase

from library.imports.archives import build_zip_index, resolve_zip_member_reference
from library.imports.batches import import_zip_file
from library.imports.covers import validate_cover_bytes
from library.imports.opf import parse_sidecar_opf
from library.imports.results import (
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_IMPORTED,
)
from library.models import Book, BookIdentifier
from tests.library.imports.helpers import (
    epub_with_cover_bytes,
    image_bytes,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ZipSidecarCoverImportTests(IsolatedMediaRootMixin, TestCase):
    def test_coverless_epub_receives_valid_sidecar_cover(self):
        cover_bytes = image_bytes("JPEG")

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes()),
                ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "cover.jpg")),
                ("dir/cover.jpg", cover_bytes),
            ),
            source_filename="books.zip",
        )

        book = _imported_book(result)
        self.assertEqual(_stored_cover_bytes(book), cover_bytes)
        self.assertTrue(book.cover_file.name.endswith(".jpg"))

    def test_valid_sidecar_cover_overrides_different_embedded_cover(self):
        embedded_cover = image_bytes("PNG")
        sidecar_cover = image_bytes("JPEG")

        result = import_zip_file(
            zip_bytes(
                (
                    "dir/book.epub",
                    epub_with_cover_bytes(cover_bytes=embedded_cover),
                ),
                ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "cover.jpg")),
                ("dir/cover.jpg", sidecar_cover),
            ),
            source_filename="books.zip",
        )

        book = _imported_book(result)
        self.assertEqual(_stored_cover_bytes(book), sidecar_cover)
        self.assertNotEqual(_stored_cover_bytes(book), embedded_cover)

    def test_invalid_sidecar_cover_falls_back_to_embedded_cover(self):
        embedded_cover = image_bytes("PNG")

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", epub_with_cover_bytes(cover_bytes=embedded_cover)),
                ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "cover.jpg")),
                ("dir/cover.jpg", b"not an image"),
            ),
            source_filename="books.zip",
        )

        self.assertEqual(_stored_cover_bytes(_imported_book(result)), embedded_cover)

    def test_missing_sidecar_cover_falls_back_to_embedded_cover(self):
        embedded_cover = image_bytes("PNG")

        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", epub_with_cover_bytes(cover_bytes=embedded_cover)),
                ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "missing.jpg")),
            ),
            source_filename="books.zip",
        )

        self.assertEqual(_stored_cover_bytes(_imported_book(result)), embedded_cover)

    def test_oversized_sidecar_cover_falls_back_to_embedded_cover(self):
        embedded_cover = image_bytes("PNG")

        with patch("library.imports.batches.MAX_COVER_IMAGE_BYTES", 1):
            result = import_zip_file(
                zip_bytes(
                    ("dir/book.epub", epub_with_cover_bytes(cover_bytes=embedded_cover)),
                    ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "cover.jpg")),
                    ("dir/cover.jpg", image_bytes("JPEG")),
                ),
                source_filename="books.zip",
            )

        self.assertEqual(_stored_cover_bytes(_imported_book(result)), embedded_cover)

    def test_unsafe_sidecar_cover_is_non_fatal(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes()),
                ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "../cover.jpg")),
                ("cover.jpg", image_bytes("JPEG")),
            ),
            source_filename="books.zip",
        )

        book = _imported_book(result)
        self.assertEqual(book.cover_file.name, "")

    def test_colliding_sidecar_cover_is_non_fatal_and_paths_stay_out_of_logs(self):
        with self.assertLogs("library.imports.archives", level="WARNING") as logs:
            result = import_zip_file(
                zip_bytes(
                    ("private/library/book.epub", minimal_epub_bytes()),
                    (
                        "private/library/metadata.opf",
                        _sidecar_opf("Sidecar Book", "cover.jpg"),
                    ),
                    ("private/library/cover.jpg", image_bytes("JPEG")),
                    ("private/library/./cover.jpg", image_bytes("PNG")),
                ),
                source_filename="books.zip",
            )

        book = next(item.book for item in result.items if item.status == IMPORT_STATUS_IMPORTED)
        self.assertEqual(book.cover_file.name, "")
        joined_logs = "\n".join(logs.output)
        self.assertNotIn("private/library", joined_logs)
        self.assertNotIn("cover.jpg", joined_logs)
        self.assertNotIn(
            "private/library",
            "\n".join(item.safe_message for item in result.items),
        )

    def test_sidecar_cover_storage_failure_is_non_fatal(self):
        with (
            patch(
                "library.imports.epub.replace_book_cover",
                side_effect=RuntimeError("storage failed"),
            ),
            self.assertLogs("library.imports.epub", level="WARNING") as logs,
        ):
            result = import_zip_file(
                zip_bytes(
                    ("dir/book.epub", minimal_epub_bytes()),
                    ("dir/metadata.opf", _sidecar_opf("Sidecar Book", "cover.jpg")),
                    ("dir/cover.jpg", image_bytes("JPEG")),
                ),
                source_filename="books.zip",
            )

        book = _imported_book(result)
        self.assertEqual(book.cover_file.name, "")
        self.assertNotIn("dir/", "\n".join(logs.output))
        self.assertNotIn("cover.jpg", "\n".join(logs.output))

    def test_duplicate_checksum_does_not_attach_sidecar_cover(self):
        epub_bytes = minimal_epub_bytes()
        first = import_zip_file(
            zip_bytes(("book.epub", epub_bytes)),
            source_filename="first.zip",
        )

        second = import_zip_file(
            zip_bytes(
                ("book.epub", epub_bytes),
                ("metadata.opf", _sidecar_opf("Changed", "cover.jpg")),
                ("cover.jpg", image_bytes("JPEG")),
            ),
            source_filename="second.zip",
        )

        book = first.items[0].book
        book.refresh_from_db()
        self.assertEqual(second.items[0].status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(book.cover_file.name, "")
        self.assertEqual(book.title, "Sample EPUB")

    def test_duplicate_checksum_does_not_replace_existing_cover_from_sidecar(self):
        epub_bytes = minimal_epub_bytes()
        original_cover = image_bytes("PNG")
        replacement_cover = image_bytes("JPEG")
        first = import_zip_file(
            zip_bytes(
                ("book.epub", epub_bytes),
                ("metadata.opf", _sidecar_opf("Original", "cover.png")),
                ("cover.png", original_cover),
            ),
            source_filename="first.zip",
        )

        second = import_zip_file(
            zip_bytes(
                ("book.epub", epub_bytes),
                ("metadata.opf", _sidecar_opf("Replacement", "cover.jpg")),
                ("cover.jpg", replacement_cover),
            ),
            source_filename="second.zip",
        )

        book = first.items[0].book
        book.refresh_from_db()
        self.assertEqual(second.items[0].status, IMPORT_STATUS_DUPLICATE)
        self.assertEqual(_stored_cover_bytes(book), original_cover)
        self.assertNotEqual(_stored_cover_bytes(book), replacement_cover)

    def test_shared_identifier_imports_new_book_with_sidecar_cover(self):
        existing = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )

        result = import_zip_file(
            zip_bytes(
                ("book.epub", minimal_epub_bytes()),
                (
                    "metadata.opf",
                    _sidecar_opf(
                        "Conflict",
                        "cover.jpg",
                        identifier=(
                            '<dc:identifier opf:scheme="ISBN">'
                            "978-0-00-000001-1</dc:identifier>"
                        ),
                    ),
                ),
                ("cover.jpg", image_bytes("JPEG")),
            ),
            source_filename="books.zip",
        )

        existing.refresh_from_db()
        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertTrue(result.items[0].book.cover_file.name)
        self.assertEqual(existing.cover_file.name, "")


class SmallCalibreLibrarySidecarCoverFixtureTests(TestCase):
    def test_fixture_opfs_reference_adjacent_valid_cover_jpegs(self):
        fixture = Path(__file__).resolve().parents[2] / "fixtures/library/small_calibre_library.zip"

        with zipfile.ZipFile(fixture, "r") as archive:
            index = build_zip_index(archive.infolist())
            opf_names = sorted(
                name for names in index.opfs_by_dir.values() for name in names
            )

            self.assertEqual(len(opf_names), 5)
            for opf_name in opf_names:
                with self.subTest(opf=opf_name):
                    parsed = parse_sidecar_opf(archive.read(opf_name))
                    member = resolve_zip_member_reference(
                        base_member=opf_name,
                        href=parsed.cover_href,
                        members_index=index.members_index,
                    )
                    self.assertEqual(parsed.cover_href, "cover.jpg")
                    self.assertIsNotNone(member)
                    cover = validate_cover_bytes(archive.read(member.archive_name))
                    self.assertIsNotNone(cover)
                    self.assertEqual(cover.extension, ".jpg")


def _sidecar_opf(title: str, cover_href: str, *, identifier: str = "") -> bytes:
    return f"""
    <package xmlns="http://www.idpf.org/2007/opf"
             xmlns:opf="http://www.idpf.org/2007/opf">
      <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{title}</dc:title>
        <dc:creator>Sidecar Author</dc:creator>
        {identifier}
      </metadata>
      <guide><reference type="cover" href="{cover_href}"/></guide>
    </package>
    """.encode()


def _imported_book(result):
    item = next(item for item in result.items if item.status == IMPORT_STATUS_IMPORTED)
    return item.book


def _stored_cover_bytes(book: Book) -> bytes:
    with book.cover_file.open("rb") as fp:
        return fp.read()
