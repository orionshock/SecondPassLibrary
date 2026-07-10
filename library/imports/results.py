from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_DUPLICATE = "duplicate"
IMPORT_STATUS_CONFLICT = "conflict"
IMPORT_STATUS_FAILED = "failed"
IMPORT_STATUS_SKIPPED = "skipped"


@dataclass(frozen=True)
class ImportItemResult:
    status: str
    source_label: str
    book: object | None = None
    safe_message: str = ""
    operator_detail: str = ""


@dataclass
class ImportBatchResult:
    source_type: str
    source_label: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    items: list[ImportItemResult] = field(default_factory=list)

    @property
    def total_found(self) -> int:
        return len(self.items)

    @property
    def imported_count(self) -> int:
        return self.count_status(IMPORT_STATUS_IMPORTED)

    @property
    def duplicate_count(self) -> int:
        return self.count_status(IMPORT_STATUS_DUPLICATE)

    @property
    def conflict_count(self) -> int:
        return self.count_status(IMPORT_STATUS_CONFLICT)

    @property
    def failed_count(self) -> int:
        return self.count_status(IMPORT_STATUS_FAILED)

    @property
    def skipped_count(self) -> int:
        return self.count_status(IMPORT_STATUS_SKIPPED)

    def count_status(self, status: str) -> int:
        return sum(1 for item in self.items if item.status == status)
