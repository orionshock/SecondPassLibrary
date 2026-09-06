from __future__ import annotations

from io import BytesIO, StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import TestCase

from library.imports.cli_runner import MIN_DESTINATION_FREE_BYTES, run_cli_import
from library.imports.cli_sources import (
    ImportSourceAdapter,
    ImportSourceEvent,
    PreparedImportCandidate,
)
from library.imports.results import IMPORT_STATUS_IMPORTED, ImportItemResult
from library.groups.public_group import get_public_group
from library.models import Book, BookGroupAssignment, BookIdentifier
from tests.library.imports.helpers import (
    ImportPersistenceFixtureMixin,
    image_bytes,
    metadata_xml,
    minimal_epub_bytes,
    sidecar_opf_xml,
    zip_bytes,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ImportLibraryCommandTests(
    IsolatedMediaRootMixin,
    ImportPersistenceFixtureMixin,
    TestCase,
):
    def test_folder_of_zip_recurses_deterministically_and_preserves_direct_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(
                root / "z" / "second.epub",
                minimal_epub_bytes(metadata_xml=metadata_xml("Second")),
            )
            _write_file(
                root / "a" / "first.zip",
                zip_bytes(
                    (
                        "first.epub",
                        minimal_epub_bytes(metadata_xml=metadata_xml("First")),
                    )
                ).getvalue(),
            )
            output = StringIO()

            call_command("import_library_folder_of_zip", str(root), stdout=output)

        text = output.getvalue()
        self.assertLess(text.index("a/first.zip"), text.index("z/second.epub"))
        self.assertIn("Imported", text)
        self.assertIn("Import summary", text)
        self.assertEqual(Book.objects.count(), 2)

    def test_folder_of_zip_retains_single_epub_and_zip_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            epub = _write_file(root / "one.epub", minimal_epub_bytes())
            archive = _write_file(
                root / "two.zip",
                zip_bytes(
                    (
                        "two.epub",
                        minimal_epub_bytes(metadata_xml=metadata_xml("Two")),
                    )
                ).getvalue(),
            )

            call_command("import_library_folder_of_zip", str(epub), stdout=StringIO())
            call_command("import_library_folder_of_zip", str(archive), stdout=StringIO())

        self.assertEqual(Book.objects.count(), 2)

    def test_folder_of_zip_duplicate_is_successful_and_reported(self):
        data = minimal_epub_bytes()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "one.epub", data)
            _write_file(root / "two.epub", data)
            output = StringIO()

            call_command("import_library_folder_of_zip", str(root), stdout=output)

        self.assertIn("Duplicate", output.getvalue())
        self.assertEqual(Book.objects.count(), 1)

    def test_folder_of_zip_empty_directory_succeeds_with_zero_summary(self):
        with TemporaryDirectory() as tmp:
            output = StringIO()

            call_command("import_library_folder_of_zip", tmp, stdout=output)

        self.assertIn("Imported", output.getvalue())
        self.assertIn("0", output.getvalue())

    def test_folder_of_zip_unsupported_or_missing_path_is_fatal(self):
        with TemporaryDirectory() as tmp:
            unsupported = _write_file(Path(tmp) / "notes.txt", b"notes")
            with self.assertRaises(CommandError):
                call_command(
                    "import_library_folder_of_zip",
                    str(unsupported),
                    stdout=StringIO(),
                )
        with self.assertRaises(CommandError):
            call_command(
                "import_library_folder_of_zip",
                "missing.epub",
                stdout=StringIO(),
            )

    def test_folder_of_zip_mixed_failure_continues_then_exits_nonzero(self):
        with TemporaryDirectory() as tmp:
            archive = _write_file(
                Path(tmp) / "mixed.zip",
                zip_bytes(
                    ("bad.epub", b"not an epub"),
                    ("good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
                ).getvalue(),
            )
            output = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library_folder_of_zip", str(archive), stdout=output)

        text = output.getvalue()
        self.assertIn("Failed", text)
        self.assertIn("Good", text)
        self.assertIn("Import summary", text)
        self.assertEqual(Book.objects.get().title, "Good")

    def test_folder_of_zip_conflict_is_structured_and_nonzero(self):
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

            with self.assertRaises(CommandError):
                call_command("import_library_folder_of_zip", str(path), stdout=output)

        self.assertIn("Conflict", output.getvalue())
        self.assertEqual(Book.objects.count(), 1)

    def test_folder_of_zip_uses_canonical_public_group_persistence(self):
        with TemporaryDirectory() as tmp:
            path = _write_file(Path(tmp) / "sample.epub", minimal_epub_bytes())

            call_command("import_library_folder_of_zip", str(path), stdout=StringIO())

        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=Book.objects.get(),
                group=get_public_group(),
            ).exists()
        )

    def test_aio_zip_imports_nested_candidates_with_opf_and_adjacent_cover(self):
        cover = image_bytes("JPEG")
        data = zip_bytes(
            (
                "author/book/book.epub",
                minimal_epub_bytes(metadata_xml=metadata_xml("Embedded")),
            ),
            ("author/book/metadata.opf", sidecar_opf_xml("Sidecar").encode()),
            ("author/book/cover.jpg", cover),
        ).getvalue()
        with TemporaryDirectory() as tmp:
            archive = _write_file(Path(tmp) / "library.zip", data)
            output = StringIO()

            with patch("zipfile.ZipFile.extractall") as extractall:
                call_command("import_library_aio_zip", str(archive), stdout=output)

        extractall.assert_not_called()
        book = Book.objects.get()
        self.assertEqual(book.title, "Sidecar")
        self.assertTrue(book.cover_file.name)
        self.assertIn("author/book/book.epub", output.getvalue())

    def test_aio_zip_rejects_ambiguous_directory_and_continues(self):
        data = zip_bytes(
            ("ambiguous/one.epub", minimal_epub_bytes(metadata_xml=metadata_xml("One"))),
            ("ambiguous/two.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Two"))),
            ("good/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
        ).getvalue()
        with TemporaryDirectory() as tmp:
            archive = _write_file(Path(tmp) / "library.zip", data)
            output = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library_aio_zip", str(archive), stdout=output)

        text = output.getvalue()
        self.assertIn("multiple EPUB files", text)
        self.assertIn("Good", text)
        self.assertEqual(Book.objects.get().title, "Good")

    def test_aio_zip_skips_opf_without_epub(self):
        with TemporaryDirectory() as tmp:
            archive = _write_file(
                Path(tmp) / "library.zip",
                zip_bytes(
                    ("metadata-only/metadata.opf", sidecar_opf_xml("No EPUB").encode())
                ).getvalue(),
            )
            output = StringIO()

            call_command("import_library_aio_zip", str(archive), stdout=output)

        self.assertIn("Metadata exists without an EPUB", output.getvalue())
        self.assertFalse(Book.objects.exists())

    def test_aio_zip_container_limit_is_separate_from_web_upload_limit(self):
        from library.imports.aio_zip_source import MAX_AIO_ZIP_COMPRESSED_BYTES
        from library.imports.views import MAX_IMPORT_UPLOAD_BYTES

        self.assertGreater(MAX_AIO_ZIP_COMPRESSED_BYTES, MAX_IMPORT_UPLOAD_BYTES)

    def test_aio_zip_member_limit_is_a_fatal_source_error(self):
        with TemporaryDirectory() as tmp:
            archive = _write_file(
                Path(tmp) / "library.zip",
                zip_bytes(("book.epub", minimal_epub_bytes())).getvalue(),
            )

            with (
                patch("library.imports.aio_zip_source.MAX_AIO_ZIP_MEMBERS", 0),
                self.assertRaises(CommandError),
            ):
                call_command("import_library_aio_zip", str(archive), stdout=StringIO())

        self.assertFalse(Book.objects.exists())

    def test_aio_zip_unsafe_member_is_a_fatal_source_error(self):
        data = zip_bytes(
            ("../unsafe.epub", minimal_epub_bytes()),
            ("good/book.epub", minimal_epub_bytes()),
        ).getvalue()
        with TemporaryDirectory() as tmp:
            archive = _write_file(Path(tmp) / "library.zip", data)

            with self.assertRaises(CommandError):
                call_command("import_library_aio_zip", str(archive), stdout=StringIO())

        self.assertFalse(Book.objects.exists())

    def test_aio_zip_encrypted_member_is_a_fatal_source_error(self):
        data = zip_bytes(("book/book.epub", minimal_epub_bytes())).getvalue()
        with TemporaryDirectory() as tmp:
            archive = _write_file(
                Path(tmp) / "library.zip",
                _mark_first_central_directory_member_encrypted(data),
            )

            with self.assertRaises(CommandError):
                call_command("import_library_aio_zip", str(archive), stdout=StringIO())

        self.assertFalse(Book.objects.exists())

    def test_tree_imports_nested_candidate_with_opf_and_cover(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            book_dir = root / "author" / "book"
            _write_file(
                book_dir / "book.epub",
                minimal_epub_bytes(metadata_xml=metadata_xml("Embedded")),
            )
            _write_file(book_dir / "metadata.opf", sidecar_opf_xml("Tree Sidecar").encode())
            _write_file(book_dir / "cover.jpg", image_bytes("JPEG"))
            output = StringIO()

            call_command("import_library_tree", str(root), stdout=output)

        book = Book.objects.get()
        self.assertEqual(book.title, "Tree Sidecar")
        self.assertTrue(book.cover_file.name)
        self.assertIn("author/book/book.epub", output.getvalue())

    def test_tree_reports_missing_and_ambiguous_epubs_then_continues(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "metadata-only" / "metadata.opf", sidecar_opf_xml("None").encode())
            _write_file(root / "ambiguous" / "one.epub", minimal_epub_bytes())
            _write_file(
                root / "ambiguous" / "two.epub",
                minimal_epub_bytes(metadata_xml=metadata_xml("Two")),
            )
            _write_file(
                root / "good" / "book.epub",
                minimal_epub_bytes(metadata_xml=metadata_xml("Good")),
            )
            output = StringIO()

            with self.assertRaises(CommandError):
                call_command("import_library_tree", str(root), stdout=output)

        text = output.getvalue()
        self.assertIn("Metadata exists without an EPUB", text)
        self.assertIn("multiple EPUB files", text)
        self.assertEqual(Book.objects.get().title, "Good")

    def test_tree_does_not_follow_directory_symlinks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            outside = Path(tmp) / "outside"
            _write_file(outside / "book.epub", minimal_epub_bytes())
            root.mkdir()
            try:
                os.symlink(outside, root / "linked", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Directory symlinks unavailable: {exc}")
            output = StringIO()

            call_command("import_library_tree", str(root), stdout=output)

        self.assertFalse(Book.objects.exists())
        self.assertIn("Skipped symlinks", output.getvalue())

    def test_low_destination_space_stops_before_pipeline(self):
        with TemporaryDirectory() as tmp:
            epub = _write_file(Path(tmp) / "book.epub", minimal_epub_bytes())
            output = StringIO()

            with (
                patch("library.imports.cli_runner._destination_free_bytes", return_value=1),
                patch("library.imports.cli_runner.import_epub_file") as importer,
                self.assertRaises(CommandError),
            ):
                call_command("import_library_folder_of_zip", str(epub), stdout=output)

        importer.assert_not_called()
        self.assertIn("Destination free space", output.getvalue())

    def test_all_three_commands_use_the_shared_candidate_pipeline(self):
        cases = []
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            direct = _write_file(root / "direct.epub", minimal_epub_bytes())
            aio = _write_file(
                root / "aio.zip",
                zip_bytes(("book/book.epub", minimal_epub_bytes())).getvalue(),
            )
            tree = root / "tree"
            _write_file(tree / "book" / "book.epub", minimal_epub_bytes())
            cases.extend(
                (
                    ("import_library_folder_of_zip", direct, "folder_of_zip"),
                    ("import_library_aio_zip", aio, "aio_zip"),
                    ("import_library_tree", tree, "tree"),
                )
            )
            for command_name, source, method in cases:
                with (
                    self.subTest(command=command_name),
                    patch(
                        "library.imports.cli_runner.import_epub_file",
                        return_value=ImportItemResult(
                            status=IMPORT_STATUS_IMPORTED,
                            source_label="book.epub",
                        ),
                    ) as importer,
                ):
                    call_command(command_name, str(source), stdout=StringIO())
                    self.assertEqual(importer.call_count, 1)
                    self.assertEqual(importer.call_args.kwargs["source_method"], method)


class SequentialImportRunnerTests(TestCase):
    def test_result_is_printed_before_source_advances(self):
        output = StringIO()
        command = BaseCommand(stdout=output)
        source = _ObservingSource(output)

        with (
            patch("library.imports.cli_runner._destination_free_bytes", return_value=10**12),
            patch(
                "library.imports.cli_runner.import_epub_file",
                return_value=ImportItemResult(
                    status=IMPORT_STATUS_IMPORTED,
                    source_label="book.epub",
                    title="Readable Result",
                ),
            ),
        ):
            run_cli_import(command=command, source=source)

        self.assertTrue(source.observed_completed_output)
        self.assertNotIn("\x1b[", output.getvalue())

    def test_keyboard_interrupt_prints_last_completed_candidate_and_propagates(self):
        output = StringIO()
        command = BaseCommand(stdout=output)
        source = _ObservingSource(output)

        with (
            patch("library.imports.cli_runner._destination_free_bytes", return_value=10**12),
            patch(
                "library.imports.cli_runner.import_epub_file",
                side_effect=KeyboardInterrupt,
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            run_cli_import(command=command, source=source)

        self.assertIn("Interrupted after candidate 0", output.getvalue())

    def test_free_space_loss_before_candidate_import_stops_without_persisting(self):
        output = StringIO()
        command = BaseCommand(stdout=output)
        source = _EventsSource([_candidate_event("book.epub")])

        with (
            patch(
                "library.imports.cli_runner._destination_free_bytes",
                side_effect=[MIN_DESTINATION_FREE_BYTES * 2, 1],
            ),
            patch("library.imports.cli_runner.import_epub_file") as importer,
            self.assertRaises(CommandError),
        ):
            run_cli_import(command=command, source=source)

        importer.assert_not_called()
        self.assertFalse(Book.objects.exists())
        self.assertIn("Destination free space", output.getvalue())

    def test_fatal_candidate_io_failure_stops_before_the_next_source(self):
        output = StringIO()
        command = BaseCommand(stdout=output)
        source = _EventsSource(
            [
                ImportSourceEvent(
                    source_label="broken.epub",
                    result=ImportItemResult(
                        status="failed",
                        source_label="broken.epub",
                        error_category="io_error",
                    ),
                ),
                _candidate_event("must-not-run.epub"),
            ]
        )

        with (
            patch(
                "library.imports.cli_runner._destination_free_bytes",
                return_value=MIN_DESTINATION_FREE_BYTES * 2,
            ),
            patch("library.imports.cli_runner.import_epub_file") as importer,
            self.assertRaises(CommandError),
        ):
            run_cli_import(command=command, source=source)

        importer.assert_not_called()
        self.assertEqual(source.yielded, ["broken.epub"])
        self.assertIn("Candidate I/O or storage failed", output.getvalue())


class _ObservingSource(ImportSourceAdapter):
    method = "test"
    limit_description = "test limits"

    def __init__(self, output):
        super().__init__(Path("test-source"))
        self.output = output
        self.observed_completed_output = False

    def iter_events(self):
        yield ImportSourceEvent(
            source_label="book.epub",
            candidate=PreparedImportCandidate(
                source_method=self.method,
                source_label="book.epub",
                epub_filename="book.epub",
                file_obj=BytesIO(b"epub"),
                file_size=4,
            ),
        )
        self.observed_completed_output = "Readable Result" in self.output.getvalue()


class _EventsSource(ImportSourceAdapter):
    method = "test"
    limit_description = "test limits"

    def __init__(self, events):
        super().__init__(Path("test-source"))
        self.events = events
        self.yielded = []

    def iter_events(self):
        for event in self.events:
            self.yielded.append(event.source_label)
            yield event


def _candidate_event(source_label: str) -> ImportSourceEvent:
    return ImportSourceEvent(
        source_label=source_label,
        candidate=PreparedImportCandidate(
            source_method="test",
            source_label=source_label,
            epub_filename=source_label,
            file_obj=BytesIO(b"epub"),
            file_size=4,
        ),
    )


def _write_file(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _mark_first_central_directory_member_encrypted(data: bytes) -> bytes:
    output = bytearray(data)
    central_header = output.find(b"PK\x01\x02")
    if central_header < 0:
        raise AssertionError("ZIP fixture has no central-directory entry")
    flag_offset = central_header + 8
    flags = int.from_bytes(output[flag_offset : flag_offset + 2], "little") | 0x1
    output[flag_offset : flag_offset + 2] = flags.to_bytes(2, "little")
    return bytes(output)
