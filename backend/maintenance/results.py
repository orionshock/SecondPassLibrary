from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


MAX_RESULT_SUMMARY_LENGTH = 1000
MAX_RESULT_COUNT_FIELDS = 12
RESULT_COUNT_LABELS = MappingProxyType(
    {
        "eligible": "Eligible pairing requests",
        "selected": "Pairing requests processed",
        "would_delete": "Pairing requests that would be deleted",
        "deleted": "Pairing requests deleted",
        "skipped_limit": "Pairing requests deferred by limit",
        "retained": "Pairing requests retained",
        "expired_stages": "Expired import stages",
        "records_deleted": "Stage records deleted",
        "files_deleted": "Stage files deleted",
        "missing_files": "Stage files already missing",
        "failures": "Cleanup failures",
        "affected_shelves": "User-owned Shelves affected",
        "removed_items": "Unavailable Shelf items removed",
        "unavailable_items": "Unavailable Shelf items",
    }
)


def result_count_label(key: str) -> str:
    return RESULT_COUNT_LABELS.get(key, key.replace("_", " ").capitalize())


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    summary: str
    counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self):
        summary = " ".join(str(self.summary).split())[:MAX_RESULT_SUMMARY_LENGTH]
        counts = {
            str(key)[:64]: int(value)
            for key, value in list(self.counts.items())[:MAX_RESULT_COUNT_FIELDS]
        }
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "counts", MappingProxyType(counts))


class MaintenanceOperationError(Exception):
    """An expected maintenance failure whose message is safe for operators."""

    def __init__(self, message: str, *, result: MaintenanceResult | None = None):
        super().__init__(message)
        self.result = result
