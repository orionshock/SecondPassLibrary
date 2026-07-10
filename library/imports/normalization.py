from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

from library.imports.results import ImportIdentifier, ImportTag


DATE_PRECISION_YEAR = "year"
DATE_PRECISION_MONTH = "month"
DATE_PRECISION_DAY = "day"

SCHEME_ISBN_10 = "isbn_10"
SCHEME_ISBN_13 = "isbn_13"
SCHEME_ASIN = "asin"
SCHEME_DOI = "doi"
SCHEME_OCLC = "oclc"
SCHEME_LCCN = "lccn"
SCHEME_OPENLIBRARY = "openlibrary"
SCHEME_CALIBRE = "calibre"
SCHEME_EPUB_UID = "epub_uid"
SCHEME_PUBLISHER = "publisher"
SCHEME_URI = "uri"
SCHEME_UUID = "uuid"
SCHEME_OTHER = "other"

_WHITESPACE_RE = re.compile(r"\s+")
_ISBN_CHARS_RE = re.compile(r"[^0-9Xx]")
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)


def collapse_whitespace(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def fallback_sort_value(*, value: str, explicit_sort: str | None) -> str:
    sort_value = collapse_whitespace(explicit_sort)
    return sort_value or collapse_whitespace(value)


def normalize_tag_name(value: str) -> str:
    return collapse_whitespace(value).casefold()


def build_import_tags(labels: list[str]) -> list[ImportTag]:
    tags_by_normalized: dict[str, ImportTag] = {}
    for label in labels:
        name = collapse_whitespace(label)
        if not name:
            continue
        normalized = normalize_tag_name(name)
        tags_by_normalized.setdefault(
            normalized,
            ImportTag(name=name, sort_name=name, normalized_name=normalized),
        )
    return list(tags_by_normalized.values())


def normalize_identifier(*, scheme: str, value: str) -> ImportIdentifier | None:
    normalized_scheme = normalize_identifier_scheme(scheme)
    display_value = collapse_whitespace(value)
    if not display_value:
        return None
    return ImportIdentifier(
        scheme=normalized_scheme,
        value=display_value,
        normalized_value=normalize_identifier_value(
            scheme=normalized_scheme,
            value=display_value,
        ),
    )


def normalize_identifier_scheme(scheme: str | None) -> str:
    value = collapse_whitespace(scheme).casefold().replace("-", "_")
    value = value.removeprefix("scheme:")
    mapping = {
        "isbn": SCHEME_ISBN_13,
        "isbn_10": SCHEME_ISBN_10,
        "isbn10": SCHEME_ISBN_10,
        "isbn_13": SCHEME_ISBN_13,
        "isbn13": SCHEME_ISBN_13,
        "asin": SCHEME_ASIN,
        "doi": SCHEME_DOI,
        "oclc": SCHEME_OCLC,
        "lccn": SCHEME_LCCN,
        "openlibrary": SCHEME_OPENLIBRARY,
        "open_library": SCHEME_OPENLIBRARY,
        "calibre": SCHEME_CALIBRE,
        "calibre_id": SCHEME_CALIBRE,
        "epub_uid": SCHEME_EPUB_UID,
        "epub_unique_identifier": SCHEME_EPUB_UID,
        "publisher": SCHEME_PUBLISHER,
        "uri": SCHEME_URI,
        "urn": SCHEME_URI,
        "uuid": SCHEME_UUID,
    }
    return mapping.get(value, value or SCHEME_OTHER)


def normalize_identifier_value(*, scheme: str, value: str) -> str:
    text = collapse_whitespace(value)
    if scheme in {SCHEME_ISBN_10, SCHEME_ISBN_13}:
        return _ISBN_CHARS_RE.sub("", text).upper()
    if scheme == SCHEME_ASIN:
        return text.replace(" ", "").upper()
    if scheme == SCHEME_DOI:
        return _DOI_PREFIX_RE.sub("", text).casefold()
    if scheme in {SCHEME_UUID, SCHEME_URI}:
        return text.casefold()
    return text.casefold()


def parse_partial_date(value: str | None) -> tuple[int | None, int | None, int | None, str]:
    text = collapse_whitespace(value)
    if not text:
        return None, None, None, ""

    full_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", text)
    if full_match:
        year = int(full_match.group("year"))
        month = int(full_match.group("month"))
        day = int(full_match.group("day"))
        try:
            date(year, month, day)
        except ValueError:
            return None, None, None, ""
        return year, month, day, DATE_PRECISION_DAY

    month_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{2})", text)
    if month_match:
        year = int(month_match.group("year"))
        month = int(month_match.group("month"))
        if 1 <= month <= 12:
            return year, month, None, DATE_PRECISION_MONTH
        return None, None, None, ""

    year_match = re.fullmatch(r"(?P<year>\d{4})", text)
    if year_match:
        return int(year_match.group("year")), None, None, DATE_PRECISION_YEAR

    return None, None, None, ""


def parse_series_index(value: str | None) -> Decimal | None:
    text = collapse_whitespace(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
