from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from library.imports.opf import ParsedSidecarOpf
from library.imports.results import IMPORT_STATUS_FAILED, ImportItemResult


COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")


class ImportSourceFatalError(Exception):
    pass


@dataclass(frozen=True)
class PreparedImportCandidate:
    source_method: str
    source_label: str
    epub_filename: str
    file_obj: BinaryIO
    file_size: int
    metadata_label: str = ""
    sidecar_opf: ParsedSidecarOpf | None = None
    sidecar_cover_bytes: bytes | None = None


@dataclass(frozen=True)
class ImportSourceEvent:
    source_label: str
    candidate: PreparedImportCandidate | None = None
    result: ImportItemResult | None = None
    ambiguous: bool = False

    @property
    def processed_bytes(self) -> int:
        return self.candidate.file_size if self.candidate is not None else 0


class ImportSourceAdapter:
    method = "unknown"
    limit_description = ""

    def __init__(self, source: Path):
        self.source = source
        self.skipped_symlinks = 0
        self.skipped_members = 0

    @property
    def source_label(self) -> str:
        return self.source.name or str(self.source)

    def iter_events(self) -> Iterator[ImportSourceEvent]:
        raise NotImplementedError


def failed_source_event(
    source_label: str, message: str, *, error_category: str
) -> ImportSourceEvent:
    return ImportSourceEvent(
        source_label=source_label,
        result=ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=message,
            error_category=error_category,
        ),
    )


def relative_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def source_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value
