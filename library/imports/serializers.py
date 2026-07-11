from __future__ import annotations

from library.imports.results import (
    IMPORT_STATUS_CONFLICT,
    IMPORT_STATUS_DUPLICATE,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_IMPORTED,
    IMPORT_STATUS_SKIPPED,
    ImportBatchResult,
    ImportItemResult,
)


def import_item_payload(item: ImportItemResult) -> dict:
    payload = {
        "status": item.status,
        "source_label": item.source_label,
        "safe_message": item.safe_message,
    }
    if item.book is not None:
        payload["book_id"] = str(item.book.id)
    return payload


def import_batch_payload(result: ImportBatchResult) -> dict:
    return {
        "source_type": result.source_type,
        "source_label": result.source_label,
        "counts": {
            IMPORT_STATUS_IMPORTED: result.imported_count,
            IMPORT_STATUS_DUPLICATE: result.duplicate_count,
            IMPORT_STATUS_CONFLICT: result.conflict_count,
            IMPORT_STATUS_FAILED: result.failed_count,
            IMPORT_STATUS_SKIPPED: result.skipped_count,
        },
        "items": [import_item_payload(item) for item in result.items],
    }
