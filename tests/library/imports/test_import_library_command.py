from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.groups.public_group import get_public_group
from library.models import Book, BookGroupAssignment, BookIdentifier
from tests.library.imports.helpers import (
    ImportPersistenceFixtureMixin,
    metadata_xml,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ImportLibraryCommandTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_single_epub_command_imports_book(self):
        with TemporaryDirectory() as tmp:
            epub_path = _write_file(Path(tmp) / "sample.epub", minimal_epub_bytes())
            output = StringIO()

            call_command("import_library", str(epub_path), stdout=output)

        self.assertEqual(Book.objects.count(), 1)
        self.assertTrue(Book.objects.get().book_file.name)
        self.assertIn("[imported] sample.epub", output.getvalue())
        self.assertIn("imported: 1", output.getvalue())

    def test_single_zip_command_imports_book(self):
        with TemporaryDirectory() as tmp:
            zip_path = _write_file(
                Path(tmp) / "books.zip",
                zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
            )
            output = StringIO()

            call_command("import_library", str(zip_path), stdout=output)

        self.assertEqual(Book.objects.count(), 1)
        self.assertIn("[imported] sample.epub", output.getvalue())

    def test_directory_imports_epub_and_zip_in_deterministic_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "b.epub", minimal_epub_bytes(metadata_xml=metadata_xml("B Book")))
            _write_file(
                root / "a.zip",
                zip_bytes(
                    ("a.epub", minimal_epub_bytes(metadata_xml=metadata_xml("A Book")))
                ).getvalue(),
            )
            _write_file(root / "ignored.txt", b"ignored")
            output = StringIO()

            call_command("import_library", str(root), stdout=output)

        text = output.getvalue()
        self.assertLess(text.index("[imported] a.epub"), text.index("[imported] b.epub"))
        self.assertEqual(Book.objects.count(), 2)
        self.assertIn("imported: 2", text)

    def test_empty_directory_succeeds_with_zero_summary(self):
        with TemporaryDirectory() as tmp:
            output = StringIO()

            call_command("import_library", tmp, stdout=output)

        text = output.getvalue()
        self.assertIn("imported: 0", text)
        self.assertIn("duplicate: 0", text)
        self.assertIn("conflict: 0", text)
        self.assertIn("failed: 0", text)
        self.assertIn("skipped: 0", text)

    def test_directory_with_only_unsupported_files_succeeds_with_zero_summary(self):
        with TemporaryDirectory() as tmp:
            _write_file(Path(tmp) / "notes.txt", b"notes")
            output = StringIO()

            call_command("import_library", tmp, stdout=output)

        text = output.getvalue()
        self.assertIn("imported: 0", text)
        self.assertIn("failed: 0", text)

    def test_unsupported_direct_file_returns_command_error(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "notes.txt", b"notes")

            with self.assertRaises(CommandError):
                call_command("import_library", str(path), stdout=StringIO())

    def test_missing_path_returns_command_error(self):
        with self.assertRaises(CommandError):
            call_command("import_library", "missing.epub", stdout=StringIO())

    def test_unreadable_direct_file_open_failure_is_command_error(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "sample.epub", minimal_epub_bytes())

            with patch.object(Path, "open", side_effect=OSError("permission denied")):
                with self.assertRaises(CommandError) as cm:
                    call_command("import_library", str(path), stdout=StringIO())

        self.assertIn("Could not read import file", str(cm.exception))

    def test_unreadable_directory_child_becomes_failed_item(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_path = _write_file(root / "bad.epub", minimal_epub_bytes())
            _write_file(root / "good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good")))
            output = StringIO()
            error = StringIO()

            def fake_open(path, *args, **kwargs):
                if path == bad_path:
                    raise OSError("permission denied")
                return original_open(path, *args, **kwargs)

            original_open = Path.open
            with patch.object(Path, "open", fake_open):
                with self.assertRaises(CommandError):
                    call_command("import_library", str(root), stdout=output, stderr=error)

        text = output.getvalue()
        self.assertIn("[failed] bad.epub - Could not read import file.", text)
        self.assertIn("[imported] good.epub", text)
        self.assertIn("imported: 1", text)
        self.assertIn("failed: 1", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("Traceback", error.getvalue())

    def test_duplicate_checksum_reports_duplicate_and_exits_success(self):
        data = minimal_epub_bytes()
        with TemporaryDirectory() as tmp:
            first = _write_file(Path(tmp) / "first.epub", data)
            second = _write_file(Path(tmp) / "second.epub", data)
            output = StringIO()

            call_command("import_library", str(first), stdout=StringIO())
            call_command("import_library", str(second), stdout=output)

        text = output.getvalue()
        self.assertIn("[duplicate] second.epub", text)
        self.assertIn("duplicate: 1", text)
        self.assertEqual(Book.objects.count(), 1)

    def test_conflict_reports_conflict_and_exits_nonzero(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        epub = minimal_epub_bytes(
            metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                      xmlns:opf="http://www.idpf.org/2007/opf">
              <dc:title>Conflict</dc:title>
              <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
            </metadata>
            """
        )
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "conflict.epub", epub)
            output = StringIO()
            error = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library", str(path), stdout=output, stderr=error)

        self.assertIn("[conflict] conflict.epub", output.getvalue())
        self.assertIn("conflict: 1", output.getvalue())
        self.assertIn("conflicting", error.getvalue())

    def test_invalid_epub_reports_failed_and_exits_nonzero(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "bad.epub", b"not an epub")
            output = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library", str(path), stdout=output, stderr=StringIO())

        self.assertIn("[failed] bad.epub", output.getvalue())
        self.assertIn("failed: 1", output.getvalue())

    def test_mixed_zip_failure_prints_items_summary_then_exits_nonzero(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(
                Path(tmp) / "mixed.zip",
                zip_bytes(
                    ("bad.epub", b"not an epub"),
                    ("good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
                ).getvalue(),
            )
            output = StringIO()
            error = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library", str(path), stdout=output, stderr=error)

        text = output.getvalue()
        self.assertIn("[failed] bad.epub", text)
        self.assertIn("[imported] good.epub", text)
        self.assertIn("Summary:", text)
        self.assertIn("imported: 1", text)
        self.assertIn("failed: 1", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("Traceback", error.getvalue())

    def test_public_assignment_happens_through_persistence(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "sample.epub", minimal_epub_bytes())

            call_command("import_library", str(path), stdout=StringIO())

        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=Book.objects.get(),
                group=get_public_group(),
            ).exists()
        )

def _write_file(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path
