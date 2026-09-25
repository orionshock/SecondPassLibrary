from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


SessionStatus = Literal["active", "closed"]


@dataclass(frozen=True, slots=True)
class ArchiveProgress:
    location: str
    location_label: str | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class ArchiveHighlightBody:
    text: str
    prefix: str | None
    suffix: str | None
    color: str
    note: str | None


@dataclass(frozen=True, slots=True)
class ArchiveHighlight:
    client_annotation_id: str
    location: str
    location_label: str | None
    body: ArchiveHighlightBody
    created_at: str
    updated_at: str
    kind: Literal["highlight"] = "highlight"


@dataclass(frozen=True, slots=True)
class ArchiveBookmark:
    client_annotation_id: str
    location: str
    location_label: str | None
    created_at: str
    updated_at: str
    kind: Literal["bookmark"] = "bookmark"


ArchiveAnnotation: TypeAlias = ArchiveHighlight | ArchiveBookmark


@dataclass(frozen=True, slots=True)
class ArchiveReadingSession:
    source_reading_session_id: str
    name: str
    notes: str
    status: SessionStatus
    started_at: str
    closed_at: str | None
    created_at: str
    updated_at: str
    progress: ArchiveProgress | None
    annotations: tuple[ArchiveAnnotation, ...]


@dataclass(frozen=True, slots=True)
class ArchiveBook:
    file_hash: str
    title: str
    authors: tuple[str, ...]
    reading_sessions: tuple[ArchiveReadingSession, ...]


@dataclass(frozen=True, slots=True)
class MarginaliaArchive:
    type: Literal["SecondPassMarginaliaExport"]
    schema_version: Literal["0.1.0"]
    profile: str
    generated_at: str
    generator: str
    books: tuple[ArchiveBook, ...]
