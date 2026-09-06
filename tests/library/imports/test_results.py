from __future__ import annotations

from unittest import TestCase

from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_SKIPPED,
    ImportBatchResult,
    ImportItemResult,
)
from library.imports.errors import (
    InvalidEpubImportError,
    operator_import_detail,
    safe_import_message,
)
from library.imports.serializers import import_batch_payload


class ImportResultTests(TestCase):
    def test_batch_result_counts_item_statuses(self):
        result = ImportBatchResult(
            source_type="zip",
            source_label="bundle.zip",
            items=[
                ImportItemResult(status=IMPORT_STATUS_IMPORTED, source_label="a.epub"),
                ImportItemResult(status=IMPORT_STATUS_DUPLICATE, source_label="b.epub"),
                ImportItemResult(status=IMPORT_STATUS_CONFLICT, source_label="c.epub"),
                ImportItemResult(status=IMPORT_STATUS_FAILED, source_label="d.epub"),
                ImportItemResult(status=IMPORT_STATUS_SKIPPED, source_label="notes.txt"),
            ],
        )

        self.assertEqual(result.total_found, 5)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.conflict_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.skipped_count, 1)

    def test_batch_result_total_found_defaults_to_item_count(self):
        result = ImportBatchResult(
            source_type="epub",
            source_label="book.epub",
            items=[
                ImportItemResult(status=IMPORT_STATUS_IMPORTED, source_label="book.epub"),
            ],
        )

        self.assertEqual(result.total_found, 1)

    def test_batch_result_total_found_can_use_discovered_count(self):
        result = ImportBatchResult(
            source_type="zip",
            source_label="bundle.zip",
            discovered_count=3,
            items=[
                ImportItemResult(status=IMPORT_STATUS_IMPORTED, source_label="a.epub"),
                ImportItemResult(status=IMPORT_STATUS_FAILED, source_label="b.epub"),
            ],
        )

        self.assertEqual(result.total_found, 3)
        self.assertEqual(len(result.items), 2)

    def test_batch_payload_preserves_every_result_item(self):
        result = ImportBatchResult(
            source_type="zip",
            source_label="collection.zip",
            items=[
                ImportItemResult(
                    status=IMPORT_STATUS_SKIPPED,
                    source_label=f"book-{index}.epub",
                    safe_message="Skipped.",
                )
                for index in range(55)
            ],
        )

        payload = import_batch_payload(result)

        self.assertEqual(len(payload["items"]), 55)
        self.assertEqual(payload["items"][-1]["source_label"], "book-54.epub")

    def test_unexpected_operator_detail_exposes_exception_class_only(self):
        detail = operator_import_detail(Exception(r"C:\secret\path.epub"))

        self.assertEqual(detail, "Exception")

    def test_domain_error_safe_message_is_stable(self):
        error = InvalidEpubImportError("raw parser detail")

        self.assertIn("invalid or unsupported", safe_import_message(error))
        self.assertIn("try again", safe_import_message(error))
        self.assertEqual(
            operator_import_detail(error),
            "InvalidEpubImportError: raw parser detail",
        )
