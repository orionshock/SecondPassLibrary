from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ImportAuthor:
    name: str
    sort_name: str
    position: int


@dataclass(frozen=True)
class ImportSeries:
    name: str
    sort_name: str
    series_index: Decimal | None = None


@dataclass(frozen=True)
class ImportTag:
    name: str
    sort_name: str
    normalized_name: str


@dataclass(frozen=True)
class ImportIdentifier:
    scheme: str
    value: str
    normalized_value: str


@dataclass(frozen=True)
class ImportMetadata:
    title: str
    sort_title: str
    subtitle: str = ""
    authors: list[ImportAuthor] = field(default_factory=list)
    series: ImportSeries | None = None
    language: str = ""
    publisher: str = ""
    description: str = ""
    published_year: int | None = None
    published_month: int | None = None
    published_day: int | None = None
    published_date_precision: str = ""
    tags: list[ImportTag] = field(default_factory=list)
    identifiers: list[ImportIdentifier] = field(default_factory=list)
