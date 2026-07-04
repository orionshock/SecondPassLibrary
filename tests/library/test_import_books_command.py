from __future__ import annotations

from io import StringIO
from pathlib import Path
import shutil
from typing import Any, cast
import uuid
import zipfile
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.functional import empty
import django.core.files.storage as storage

from library.models import Book, BookFile
from tests.utils.books import create_file_backed_book


def _mock_epub(*, title: str = "Command ZIP Book") -> MagicMock:
    mock_book = MagicMock()
    mock_book.get_metadata.side_effect = lambda ns, name: {
        "title": [(title, {})],
        "creator": [("Command Author", {})],
        "language": [("en", {})],
    }.get(name, [])
    return mock_book


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)


class ImportBooksCommandTests(TestCase):
    def setUp(self):
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = temp_root / f"tmp_import_books_command_{uuid.uuid4().hex}"
        self.imports_dir = self.temp_dir / "imports"
        self.media_dir = self.temp_dir / "media"
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.override = override_settings(
            IMPORTS_DIR=self.imports_dir,
            MEDIA_ROOT=str(self.media_dir),
        )
        self.override.enable()

        handler = cast(Any, getattr(storage, "storages"))
        handler._storages = {}
        handler._backends = None
        setattr(cast(Any, storage.default_storage), "_wrapped", empty)

        self.zip_path = self.temp_dir / "Command Books.zip"

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_file_raises_useful_command_error(self):
        missing = self.temp_dir / "missing.zip"

        with self.assertRaises(CommandError) as cm:
            call_command("import_books", str(missing), stdout=StringIO(), stderr=StringIO())

        self.assertIn("File does not exist", str(cm.exception))
        self.assertIn(str(missing), str(cm.exception))

    def test_non_zip_path_raises_useful_command_error(self):
        bad = self.temp_dir / "book.epub"
        bad.write_bytes(b"epub")

        with self.assertRaises(CommandError) as cm:
            call_command("import_books", str(bad), stdout=StringIO(), stderr=StringIO())

        self.assertIn("File must have .zip extension", str(cm.exception))
        self.assertIn(str(bad), str(cm.exception))

    @patch("library.imports.epub.epub.read_epub")
    def test_successful_zip_imports_multiple_epubs_and_logs_summary(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        _write_zip(self.zip_path, {"a.epub": b"bytes-a", "nested/b.epub": b"bytes-b"})
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_books", level="INFO") as captured:
            call_command("import_books", str(self.zip_path), stdout=out, stderr=err)

        self.assertIn("Starting ZIP book import: Command Books.zip", out.getvalue())
        self.assertIn("Found: 2", out.getvalue())
        self.assertIn("Imported: 2", out.getvalue())
        self.assertIn("Duplicates: 0", out.getvalue())
        self.assertIn("Failed: 0", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(BookFile.objects.count(), 2)
        self.assertTrue(self.zip_path.exists())
        messages = [record.getMessage() for record in captured.records]
        self.assertIn("operator zip import started", messages)
        self.assertIn("operator zip import succeeded", messages)

    def test_duplicate_epub_reports_duplicate_count(self):
        create_file_backed_book(
            title="Existing ZIP Book",
            epub_bytes=b"dup-bytes",
            source_filename="existing.epub",
        )
        _write_zip(self.zip_path, {"dup.epub": b"dup-bytes"})
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_books", level="INFO") as captured:
            call_command("import_books", str(self.zip_path), stdout=out, stderr=err)

        self.assertIn("Found: 1", out.getvalue())
        self.assertIn("Imported: 0", out.getvalue())
        self.assertIn("Duplicates: 1", out.getvalue())
        self.assertIn("Failed: 0", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        messages = [record.getMessage() for record in captured.records]
        self.assertIn("operator zip import succeeded", messages)

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_sidecar_opf_metadata_works_through_command(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub(title="EPUB Fallback Title")
        opf_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>OPF Command Title</dc:title>
</metadata></package>
"""
        _write_zip(self.zip_path, {"dir/book.epub": b"epub-bytes", "dir/metadata.opf": opf_xml})

        call_command("import_books", str(self.zip_path), stdout=StringIO(), stderr=StringIO())

        self.assertTrue(Book.objects.filter(title="OPF Command Title").exists())
        self.assertFalse(Book.objects.filter(title="EPUB Fallback Title").exists())

    @patch("library.imports.epub.epub.read_epub")
    def test_unsafe_traversal_and_non_epub_entries_do_not_import(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        _write_zip(
            self.zip_path,
            {
                "../evil.epub": b"evil",
                "notes.txt": b"ignore",
                "safe/book.epub": b"safe",
            },
        )
        out = StringIO()

        call_command("import_books", str(self.zip_path), stdout=out, stderr=StringIO())

        self.assertIn("Found: 1", out.getvalue())
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(mock_read_epub.call_count, 1)

    @patch("library.management.commands.import_books.MAX_ZIP_MEMBERS", 1)
    def test_too_many_zip_entries_rejects_safely(self):
        _write_zip(self.zip_path, {"a.epub": b"a", "b.epub": b"b"})

        with self.assertRaises(CommandError) as cm:
            call_command("import_books", str(self.zip_path), stdout=StringIO(), stderr=StringIO())

        self.assertIn("ZIP contains more than 1 entries", str(cm.exception))
        self.assertEqual(BookFile.objects.count(), 0)
        self.assertTrue(self.zip_path.exists())

    @patch("library.management.commands.import_books.MAX_ZIP_UPLOAD_BYTES", 4)
    def test_oversized_zip_rejects_before_processing(self):
        self.zip_path.write_bytes(b"12345")

        with self.assertRaises(CommandError) as cm:
            call_command("import_books", str(self.zip_path), stdout=StringIO(), stderr=StringIO())

        self.assertIn("ZIP archive exceeds", str(cm.exception))
        self.assertEqual(BookFile.objects.count(), 0)
        self.assertTrue(self.zip_path.exists())

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.management.commands.import_books.MAX_ZIP_EPUB_MEMBER_BYTES", 4)
    def test_oversized_epub_member_becomes_failed_item(self, mock_read_epub):
        _write_zip(self.zip_path, {"big.epub": b"12345"})
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_books", level="WARNING") as captured:
            call_command("import_books", str(self.zip_path), stdout=out, stderr=err)

        self.assertIn("Found: 1", out.getvalue())
        self.assertIn("Imported: 0", out.getvalue())
        self.assertIn("Failed: 1", out.getvalue())
        self.assertIn("Failed item big.epub", err.getvalue())
        self.assertIn("uncompressed limit", err.getvalue())
        self.assertEqual(BookFile.objects.count(), 0)
        mock_read_epub.assert_not_called()
        self.assertIn(
            "operator zip import completed with failures",
            [record.getMessage() for record in captured.records],
        )

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.management.commands.import_books.MAX_ZIP_EPUB_MEMBER_BYTES", 10)
    @patch("library.management.commands.import_books.MAX_ZIP_TOTAL_EPUB_BYTES", 8)
    def test_total_epub_payload_limit_is_enforced(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        _write_zip(self.zip_path, {"a.epub": b"1111", "b.epub": b"22222"})
        out = StringIO()
        err = StringIO()

        call_command("import_books", str(self.zip_path), stdout=out, stderr=err)

        self.assertIn("Found: 2", out.getvalue())
        self.assertIn("Imported: 1", out.getvalue())
        self.assertIn("Failed: 1", out.getvalue())
        self.assertIn("total uncompressed limit", err.getvalue())
        self.assertEqual(mock_read_epub.call_count, 1)
        self.assertEqual(BookFile.objects.count(), 1)

    @patch("library.imports.epub.epub.read_epub")
    def test_malformed_epub_item_reports_safe_per_item_error(self, mock_read_epub):
        mock_read_epub.side_effect = ValueError(
            r"Failed parsing private/member.epub at C:\tmp\jobs\abc\extracted\file.epub"
        )
        _write_zip(self.zip_path, {"private/member.epub": b"bad"})
        out = StringIO()
        err = StringIO()

        call_command("import_books", str(self.zip_path), stdout=out, stderr=err)

        self.assertIn("Failed: 1", out.getvalue())
        self.assertIn("Failed item member.epub: Invalid or unsupported EPUB file.", err.getvalue())
        self.assertNotIn("private/member", err.getvalue())
        self.assertNotIn("C:\\tmp", err.getvalue())

    def test_bad_zip_structure_reports_safe_command_failure(self):
        self.zip_path.write_bytes(b"not-a-zip")

        with self.assertRaises(CommandError) as cm:
            call_command("import_books", str(self.zip_path), stdout=StringIO(), stderr=StringIO())

        self.assertEqual(str(cm.exception), "Invalid or unsupported EPUB/ZIP structure.")
        self.assertTrue(self.zip_path.exists())
