from __future__ import annotations

from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
import zipfile
from unittest.mock import patch

from django.test import TestCase

from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.imports.results import IMPORT_STATUS_FAILED, IMPORT_STATUS_IMPORTED
from library.models import Book
from tests.library.imports.helpers import (
    ImportPersistenceFixtureMixin,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class EpubArchivePreflightTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_excessive_member_count_is_rejected_before_ebooklib(self):
        self._assert_rejected_before_ebooklib(
            minimal_epub_bytes(),
            limit_patch={"MAX_EPUB_MEMBERS": 3},
        )

    def test_excessive_compressed_epub_size_is_rejected_before_ebooklib(self):
        data = minimal_epub_bytes()

        self._assert_rejected_before_ebooklib(
            data,
            limit_patch={"MAX_EPUB_COMPRESSED_BYTES": len(data) - 1},
        )

    def test_oversized_expanded_member_is_rejected_before_ebooklib(self):
        self._assert_rejected_before_ebooklib(
            minimal_epub_bytes(),
            limit_patch={"MAX_EPUB_MEMBER_UNCOMPRESSED_BYTES": 16},
        )

    def test_excessive_aggregate_expanded_size_is_rejected_before_ebooklib(self):
        data = minimal_epub_bytes()
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            aggregate_size = sum(info.file_size for info in archive.infolist())

        self._assert_rejected_before_ebooklib(
            data,
            limit_patch={"MAX_EPUB_TOTAL_UNCOMPRESSED_BYTES": aggregate_size - 1},
        )

    def test_extreme_member_compression_ratio_is_rejected_before_ebooklib(self):
        data = _epub_with_extra_member("OEBPS/bomb.xhtml", b"x" * 100_000)

        self._assert_rejected_before_ebooklib(data)

    def test_encrypted_member_is_rejected_before_ebooklib(self):
        data = _mark_first_central_directory_member_encrypted(minimal_epub_bytes())

        self._assert_rejected_before_ebooklib(data)

    def test_unsafe_member_names_are_rejected_before_ebooklib(self):
        unsafe_names = [
            "/absolute.xhtml",
            "C:/drive.xhtml",
            "../traversal.xhtml",
            "https://example.test/chapter.xhtml",
            r"OEBPS\backslash.xhtml",
        ]

        for member_name in unsafe_names:
            with self.subTest(member_name=member_name):
                self._assert_rejected_before_ebooklib(
                    _epub_with_extra_member(member_name, b"unsafe")
                )

    def test_duplicate_normalized_member_names_are_rejected_before_ebooklib(self):
        data = _epub_with_extra_member("OEBPS/./chapter.xhtml", b"duplicate")

        self._assert_rejected_before_ebooklib(data)

    def test_valid_ordinary_epub_still_imports(self):
        result = import_epub_file(
            minimal_epub_bytes(),
            source_filename="ordinary.epub",
            actor=self.actor,
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(Book.objects.count(), 1)
        self.assertTrue(result.book.book_file.name)

    def test_batch_epub_member_uses_same_preflight(self):
        batch = zip_bytes(("nested/book.epub", minimal_epub_bytes()))

        with (
            patch("library.imports.epub_validation.MAX_EPUB_MEMBERS", 3),
            patch("library.imports.epub_validation.epub.read_epub") as read_epub,
        ):
            result = import_zip_file(
                batch,
                source_filename="batch.zip",
                actor=self.actor,
            )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_FAILED)
        read_epub.assert_not_called()
        self._assert_no_persistent_import_artifacts()

    def _assert_rejected_before_ebooklib(
        self,
        data: bytes,
        *,
        limit_patch: dict[str, int] | None = None,
    ) -> None:
        limit_context = (
            patch.multiple("library.imports.epub_validation", **limit_patch)
            if limit_patch
            else nullcontext()
        )
        with (
            limit_context,
            patch("library.imports.epub_validation.epub.read_epub") as read_epub,
        ):
            result = import_epub_file(
                data,
                source_filename="unsafe.epub",
                actor=self.actor,
            )

        self.assertEqual(result.status, IMPORT_STATUS_FAILED)
        self.assertEqual(result.safe_message, "Invalid or unsupported EPUB file.")
        read_epub.assert_not_called()
        self._assert_no_persistent_import_artifacts()

    def _assert_no_persistent_import_artifacts(self) -> None:
        self.assertFalse(Book.objects.exists())
        self.assertEqual(
            [path for path in Path(self._media_root).rglob("*") if path.is_file()],
            [],
        )


def _epub_with_extra_member(name: str, data: bytes) -> bytes:
    write_name = name.replace("\\", "/")
    output = BytesIO(minimal_epub_bytes())
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(write_name, data)
    result = output.getvalue()
    if write_name != name:
        encoded_write_name = write_name.encode()
        encoded_name = name.encode()
        central_name_offset = result.rfind(encoded_write_name)
        if central_name_offset < 0:
            raise AssertionError("EPUB fixture has no matching central-directory name")
        result = (
            result[:central_name_offset]
            + encoded_name
            + result[central_name_offset + len(encoded_write_name) :]
        )
    return result


def _mark_first_central_directory_member_encrypted(data: bytes) -> bytes:
    output = bytearray(data)
    central_header = output.find(b"PK\x01\x02")
    if central_header < 0:
        raise AssertionError("EPUB fixture has no central-directory entry")
    flag_offset = central_header + 8
    flags = int.from_bytes(output[flag_offset : flag_offset + 2], "little") | 0x1
    output[flag_offset : flag_offset + 2] = flags.to_bytes(2, "little")
    return bytes(output)
