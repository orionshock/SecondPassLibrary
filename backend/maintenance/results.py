from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


MAX_RESULT_SUMMARY_LENGTH = 1000
MAX_RESULT_COUNT_FIELDS = 12


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
