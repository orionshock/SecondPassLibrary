from io import BytesIO
from unittest.mock import patch

from library.imports.archives import ZipImportCandidate, ZipImportPlan, plan_zip_import
from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from tests.library.imports.helpers import (
    epub_with_cover_bytes,
    image_bytes,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.library.imports.upload_api_helpers import (
    LibraryImportUploadApiTestCase,
    upload_file,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ImportOperationalLoggingTests(
    IsolatedMediaRootMixin,
    LibraryImportUploadApiTestCase,
):
    def test_successful_epub_batch_emits_one_safe_info_summary(self):
        self.login_librarian()
        data = minimal_epub_bytes()

        with self.assertLogs("library.imports.operational_logging", level="INFO") as logs:
            response = self.client.post(
                self.url,
                {"file": upload_file("private-title.epub", data)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(logs.output), 1)
        message = logs.output[0]
        self.assertIn("source_type=epub", message)
        self.assertIn("imported=1", message)
        self.assertIn(f"processed_bytes={len(data)}", message)
        self.assertIn(str(self.librarian.profile.id), message)
        self._assert_sensitive_values_absent(message)

    def test_successful_zip_batch_emits_one_safe_info_summary(self):
        self.login_librarian()
        data = zip_bytes(("member-name.epub", minimal_epub_bytes())).getvalue()

        with self.assertLogs("library.imports.operational_logging", level="INFO") as logs:
            response = self.client.post(
                self.url,
                {"file": upload_file("archive-name.zip", data)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("source_type=zip", logs.output[0])
        self.assertIn("imported=1", logs.output[0])
        self._assert_sensitive_values_absent(logs.output[0])

    def test_expected_duplicate_does_not_emit_error(self):
        data = minimal_epub_bytes()
        import_epub_file(
            BytesIO(data),
            source_filename="first.epub",
            actor=self.librarian,
        )

        with patch("library.imports.epub.logger.error") as error:
            result = import_epub_file(
                BytesIO(data),
                source_filename="second.epub",
                actor=self.librarian,
            )

        self.assertEqual(result.status, "duplicate")
        error.assert_not_called()

    def test_unexpected_epub_failure_emits_one_safe_error(self):
        with (
            patch("library.imports.epub._import_epub_file", side_effect=RuntimeError("secret.epub")),
            self.assertLogs("library.imports.epub", level="ERROR") as logs,
        ):
            result = import_epub_file(
                BytesIO(b"private uploaded content"),
                source_filename=r"C:\private\secret.epub",
                actor=self.librarian,
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("exception=RuntimeError", logs.output[0])
        self._assert_sensitive_values_absent(logs.output[0])

    def test_unexpected_zip_batch_failure_emits_one_safe_error(self):
        candidate = ZipImportCandidate(
            source_name="member-name.epub",
            safe_name="member-name.epub",
            source_label="member-name.epub",
            file_size=1,
        )
        with (
            patch(
                "library.imports.batches.plan_zip_import",
                return_value=ZipImportPlan(candidates=[candidate], discovered_count=1),
            ),
            patch("library.imports.batches.zipfile.ZipFile", side_effect=RuntimeError("secret.zip")),
            self.assertLogs("library.imports.batches", level="ERROR") as logs,
        ):
            result = import_zip_file(
                BytesIO(b"private uploaded content"),
                source_filename=r"C:\private\secret.zip",
                actor=self.librarian,
            )

        self.assertEqual(result.failed_count, 1)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("completion_state=partial", logs.output[0])
        self._assert_sensitive_values_absent(logs.output[0])

    def test_unsafe_and_colliding_members_emit_aggregate_warning_only(self):
        data = zip_bytes(
            ("../unsafe-member.epub", b"bad"),
            ("dir/book.epub", b"one"),
            ("dir\\book.epub", b"two"),
        )

        with self.assertLogs("library.imports.archives", level="WARNING") as logs:
            plan_zip_import(data)

        self.assertEqual(len(logs.output), 1)
        self.assertIn("unsafe=1", logs.output[0])
        self.assertIn("collisions=2", logs.output[0])
        self._assert_sensitive_values_absent(logs.output[0])

    def test_optional_cover_storage_failure_warns_without_source_data(self):
        data = epub_with_cover_bytes(cover_bytes=image_bytes())

        with (
            patch(
                "library.imports.epub.attach_cover_to_book",
                side_effect=OSError(r"C:\private\cover.png"),
            ),
            self.assertLogs("library.imports.epub", level="WARNING") as logs,
        ):
            result = import_epub_file(
                BytesIO(data),
                source_filename="private-title.epub",
                actor=self.librarian,
            )

        self.assertEqual(result.status, "imported")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Optional cover storage failed", logs.output[0])
        self._assert_sensitive_values_absent(logs.output[0])

    def _assert_sensitive_values_absent(self, message):
        for value in (
            "private-title.epub",
            "archive-name.zip",
            "member-name.epub",
            "unsafe-member.epub",
            "dir/book.epub",
            "secret.epub",
            "secret.zip",
            "Sample EPUB",
            "private uploaded content",
            "C:\\private",
        ):
            self.assertNotIn(value, message)
