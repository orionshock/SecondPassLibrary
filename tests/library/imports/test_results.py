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
