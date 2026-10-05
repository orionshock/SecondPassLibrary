from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.db import IntegrityError

from library.imports.archives import ZipImportCandidate, ZipImportPlan, plan_zip_import
from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.models import Author, Book, BookIdentifier, Series
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

        with self.assertNoLogs("library.imports.epub", level="ERROR"):
            result = import_epub_file(
                BytesIO(data),
                source_filename="second.epub",
                actor=self.librarian,
            )

        self.assertEqual(result.status, "duplicate")

    def test_shared_identifier_metadata_emits_no_warning_or_error(self):
        existing = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        data = minimal_epub_bytes(metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                      xmlns:opf="http://www.idpf.org/2007/opf">
              <dc:title>Shared Identifier</dc:title>
              <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
            </metadata>
        """)

        with self.assertNoLogs("library.imports", level="WARNING"):
            result = import_epub_file(
                BytesIO(data),
                source_filename="shared.epub",
            )

        self.assertEqual(result.status, "imported")

    def test_ambiguous_author_conflict_logs_bounded_resolution_context(self):
        authors = [
            Author.objects.create(
                name=name,
                sort_name=name,
                normalized_name="shared author",
            )
            for name in ("Shared Author", "SHARED AUTHOR")
        ]
        data = minimal_epub_bytes(metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>Ambiguous Author Book</dc:title>
              <dc:creator> shared   author </dc:creator>
            </metadata>
        """)

        with self.assertLogs("library.imports.epub", level="WARNING") as logs:
            result = import_epub_file(
                BytesIO(data),
                source_filename=r"C:\private\author.epub",
                source_label="safe-author.epub",
                source_method="tree",
                candidate_ordinal=7,
            )

        message = " ".join(logs.output)
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.error_category, "author_ambiguous")
        self.assertIn("source_method=tree", message)
        self.assertIn("source=safe-author.epub", message)
        self.assertIn("candidate_ordinal=7", message)
        self.assertIn("category=author_ambiguous", message)
        self.assertIn("entity_type=Author", message)
        self.assertIn("incoming_name=shared author", message)
        self.assertIn("normalized_name=shared author", message)
        self.assertIn("match_count=2", message)
        for author in authors:
            self.assertIn(str(author.pk), message)
        self.assertIn("candidate_persisted=false", message)
        self.assertIn("resolution=operator_cleanup_required", message)
        self.assertNotIn("C:\\private", message)

    def test_ambiguous_series_conflict_logs_bounded_resolution_context(self):
        series_rows = [
            Series.objects.create(
                name=name,
                sort_name=name,
                normalized_name="chronicles",
            )
            for name in ("Chronicles", "CHRONICLES")
        ]
        data = minimal_epub_bytes(metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>Ambiguous Series Book</dc:title>
              <dc:creator>Writer</dc:creator>
              <meta name="calibre:series" content=" Chronicles "/>
            </metadata>
        """)

        with self.assertLogs("library.imports.epub", level="WARNING") as logs:
            result = import_epub_file(
                BytesIO(data),
                source_filename="series.epub",
                source_method="web",
            )

        message = " ".join(logs.output)
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.error_category, "series_ambiguous")
        self.assertIn("category=series_ambiguous", message)
        self.assertIn("entity_type=Series", message)
        self.assertIn("incoming_name=Chronicles", message)
        self.assertIn("normalized_name=chronicles", message)
        self.assertIn("match_count=2", message)
        for series in series_rows:
            self.assertIn(str(series.pk), message)
        self.assertIn("candidate_persisted=false", message)
        self.assertIn("resolution=operator_cleanup_required", message)

    def test_candidate_pipeline_logs_bounded_lifecycle_context(self):
        with self.assertLogs("library.imports.epub", level="INFO") as logs:
            result = import_epub_file(
                BytesIO(minimal_epub_bytes()),
                source_filename="private-title.epub",
                source_label="private/path/private-title.epub",
                source_method="tree",
                actor=self.librarian,
            )

        self.assertEqual(result.status, "imported")
        self.assertEqual(result.title, "Sample EPUB")
        self.assertEqual(result.authors, ("Sample Author",))
        self.assertEqual(len(logs.output), 2)
        self.assertIn("candidate received", logs.output[0].lower())
        self.assertIn("source_method=tree", logs.output[0])
        self.assertIn("status=imported", logs.output[1])
        self.assertNotIn("private-title.epub", " ".join(logs.output))

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
        self.assertIn("source_method=web", logs.output[0])
        self.assertIn("source=secret.epub", logs.output[0])
        self.assertIn("category=unexpected", logs.output[0])
        self.assertIn("transaction=not_started_or_rolled_back", logs.output[0])
        self.assertIn("storage_cleanup=handled_if_needed", logs.output[0])
        self.assertIn("retryable=false", logs.output[0])
        self.assertIn("exception=RuntimeError", logs.output[0])
        self.assertNotIn("C:\\private", logs.output[0])

    def test_persistence_failure_logs_actual_storage_cleanup_disposition(self):
        original_save = Book.save

        def fail_attachment_save(instance, *args, **kwargs):
            if kwargs.get("update_fields") == ["book_file", "updated_at"]:
                raise RuntimeError("attachment failed")
            return original_save(instance, *args, **kwargs)

        with (
            patch.object(Book, "save", new=fail_attachment_save),
            self.assertLogs("library.imports.epub", level="ERROR") as logs,
        ):
            result = import_epub_file(
                BytesIO(minimal_epub_bytes(metadata_xml="""
                    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                      <dc:title>Attachment Rollback Logging</dc:title>
                    </metadata>
                """)),
                source_filename=r"C:\private\secret.epub",
                source_label="safe.epub",
                source_method="tree",
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(logs.output), 1)
        self.assertIn("source_method=tree", logs.output[0])
        self.assertIn("source=safe.epub", logs.output[0])
        self.assertIn("category=unexpected", logs.output[0])
        self.assertIn("transaction=rolled_back", logs.output[0])
        self.assertIn("storage_cleanup=complete", logs.output[0])
        self.assertIn("retryable=false", logs.output[0])
        self.assertIn("exception=RuntimeError", logs.output[0])
        self.assertNotIn("C:\\private", logs.output[0])

    def test_cleanup_failure_is_logged_without_masking_persistence_failure(self):
        storage = Book._meta.get_field("book_file").storage
        data = minimal_epub_bytes(metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>Cleanup Failure Logging</dc:title>
            </metadata>
        """)

        with (
            patch(
                "library.imports.services._persist_authors",
                side_effect=IntegrityError("relationship failed"),
            ),
            patch.object(
                storage,
                "delete",
                side_effect=OSError(r"C:\private\stored.epub"),
            ),
            self.assertLogs("library.imports", level="WARNING") as logs,
        ):
            result = import_epub_file(
                BytesIO(data),
                source_filename="source.epub",
                source_label="safe.epub",
                source_method="tree",
            )

        message = " ".join(logs.output)
        self.assertEqual(result.status, "failed")
        self.assertIn("action=new_epub_rollback_cleanup", message)
        self.assertIn("transaction=rolled_back", message)
        self.assertIn("storage_cleanup=failed", message)
        self.assertIn("exception=IntegrityError", message)
        self.assertNotIn("C:\\private", message)

    def test_rollback_diagnosis_does_not_require_annotating_the_exception(self):
        class UnannotatableFailure(RuntimeError):
            def __setattr__(self, name, value):
                raise AttributeError("Exception attributes are read-only.")

        with (
            patch(
                "library.imports.services._persist_authors",
                side_effect=UnannotatableFailure("private persistence detail"),
            ),
            self.assertLogs("library.imports.epub", level="ERROR") as logs,
        ):
            result = import_epub_file(
                BytesIO(minimal_epub_bytes()),
                source_filename="safe.epub",
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.operator_detail, "UnannotatableFailure")
        self.assertFalse(Book.objects.exists())
        self.assertEqual(list(Path(self._media_root).rglob("*.epub")), [])
        message = " ".join(logs.output)
        self.assertIn("transaction=rolled_back", message)
        self.assertIn("storage_cleanup=complete", message)
        self.assertIn("exception=UnannotatableFailure", message)
        self.assertNotIn("private persistence detail", message)

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
                "library.imports.epub.replace_book_cover",
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
