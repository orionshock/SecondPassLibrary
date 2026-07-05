from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.models import Book
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


def _mock_epub(*, title: str = "Command Book") -> MagicMock:
    mock_book = MagicMock()
    mock_book.get_metadata.side_effect = lambda ns, name: {
        "title": [(title, {})],
        "creator": [("Command Author", {})],
        "language": [("en", {})],
    }.get(name, [])
    return mock_book


class ImportEpubCommandTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self._temporary_directory = TemporaryDirectory(prefix="secondpass-import-epub-command-")
        self.temp_dir = Path(self._temporary_directory.name)
        self.epub_path = self.temp_dir / "Command Book.epub"
        self.epub_path.write_bytes(b"command-epub")

    def tearDown(self):
        self._temporary_directory.cleanup()

    def test_missing_file_raises_useful_command_error(self):
        missing = self.temp_dir / "missing.epub"

        with self.assertRaises(CommandError) as cm:
            call_command("import_epub", str(missing), stdout=StringIO(), stderr=StringIO())

        self.assertIn("File does not exist", str(cm.exception))
        self.assertIn(str(missing), str(cm.exception))

    def test_bad_extension_raises_useful_command_error(self):
        bad = self.temp_dir / "book.txt"
        bad.write_text("not epub", encoding="utf-8")

        with self.assertRaises(CommandError) as cm:
            call_command("import_epub", str(bad), stdout=StringIO(), stderr=StringIO())

        self.assertIn("File must have .epub extension", str(cm.exception))
        self.assertIn(str(bad), str(cm.exception))

    @patch("library.imports.epub.epub.read_epub")
    def test_successful_import_prints_and_logs_success(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_epub", level="INFO") as captured:
            call_command("import_epub", str(self.epub_path), stdout=out, stderr=err)

        self.assertIn("Starting EPUB import: Command Book.epub", out.getvalue())
        self.assertIn("Successfully imported EPUB: Command Book", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        self.assertTrue(Book.objects.filter(title="Command Book").exists())
        messages = [record.getMessage() for record in captured.records]
        self.assertTrue(
            any(
                message.startswith("operator epub import started ")
                and "source_name=Command Book.epub" in message
                and "status=started" in message
                for message in messages
            )
        )
        self.assertTrue(
            any(
                message.startswith("operator epub import succeeded ")
                and "source_name=Command Book.epub" in message
                and "status=imported" in message
                for message in messages
            )
        )
        success = next(
            record
            for record in captured.records
            if record.getMessage().startswith("operator epub import succeeded ")
        )
        self.assertEqual(success.source_name, "Command Book.epub")
        self.assertEqual(success.status, "imported")

    def test_duplicate_import_prints_and_logs_duplicate(self):
        create_file_backed_book(
            title="Existing Command Book",
            epub_bytes=b"command-epub",
            source_filename="existing.epub",
        )
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_epub", level="INFO") as captured:
            call_command("import_epub", str(self.epub_path), stdout=out, stderr=err)

        self.assertIn("Starting EPUB import: Command Book.epub", out.getvalue())
        self.assertIn("EPUB already exists: Existing Command Book", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        messages = [record.getMessage() for record in captured.records]
        self.assertTrue(
            any(
                message.startswith("operator epub import duplicate ")
                and "source_name=Command Book.epub" in message
                and "status=duplicate" in message
                for message in messages
            )
        )
        duplicate = next(
            record
            for record in captured.records
            if record.getMessage().startswith("operator epub import duplicate ")
        )
        self.assertEqual(duplicate.source_name, "Command Book.epub")
        self.assertEqual(duplicate.status, "duplicate")

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.management.commands.import_epub.MAX_SINGLE_EPUB_UPLOAD_BYTES", 4)
    def test_oversized_file_warns_but_proceeds(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub(title="Oversize Command Book")
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_epub", level="WARNING") as captured:
            call_command("import_epub", str(self.epub_path), stdout=out, stderr=err)

        self.assertIn("Successfully imported EPUB: Oversize Command Book", out.getvalue())
        self.assertIn("exceeds the normal Product/API", err.getvalue())
        self.assertTrue(Book.objects.filter(title="Oversize Command Book").exists())
        messages = [record.getMessage() for record in captured.records]
        self.assertTrue(
            any(
                message.startswith("operator epub import size_warning ")
                and "source_name=Command Book.epub" in message
                and "status=size_warning" in message
                and "Product/API" in message
                for message in messages
            )
        )

    @patch("library.management.commands.import_epub.import_epub")
    def test_unexpected_import_failure_reports_clear_message_without_traceback_dump(self, mock_import):
        mock_import.side_effect = RuntimeError(
            r"Traceback parsing C:\secret\private.epub with noisy internals"
        )
        out = StringIO()
        err = StringIO()

        with self.assertLogs("library.management.commands.import_epub", level="ERROR") as captured:
            with self.assertRaises(CommandError) as cm:
                call_command("import_epub", str(self.epub_path), stdout=out, stderr=err)

        self.assertIn("Starting EPUB import: Command Book.epub", out.getvalue())
        self.assertIn("Failed to import EPUB: Invalid or unsupported EPUB file.", err.getvalue())
        self.assertEqual(str(cm.exception), "Invalid or unsupported EPUB file.")
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn("C:\\secret", err.getvalue())
        failure = captured.records[0]
        self.assertTrue(
            failure.getMessage().startswith("operator epub import failed_unexpectedly ")
        )
        self.assertIn("source_name=Command Book.epub", failure.getMessage())
        self.assertIn("status=failed", failure.getMessage())
        self.assertIn("message=Invalid or unsupported EPUB file.", failure.getMessage())
        self.assertEqual(failure.source_name, "Command Book.epub")
        self.assertEqual(failure.safe_message, "Invalid or unsupported EPUB file.")
        self.assertIsNotNone(failure.exc_info)

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.imports.book_import.BookFile.objects.create")
    def test_bookfile_creation_failure_rolls_back_book_row(
        self, mock_book_file_create, mock_read_epub
    ):
        mock_read_epub.return_value = _mock_epub(title="Rollback Command Book")
        mock_book_file_create.side_effect = RuntimeError("database write failed")

        with self.assertRaises(CommandError):
            call_command("import_epub", str(self.epub_path), stdout=StringIO(), stderr=StringIO())

        self.assertFalse(Book.objects.filter(title="Rollback Command Book").exists())
