from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
import re
from typing import Any, Callable, Optional

from ebooklib import epub

from .book_import import persist_new_imported_book
from .opf import (
    extract_opf_sidecar_metadata,
    merge_metadata,
    try_set_book_cover_from_sidecar_opf,
)
from ..cover_services import extract_epub_embedded_cover_to_book
from ..models import Book, BookFile, BookIdentifier


class ImportStatus(str, Enum):
    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass
class ImportResult:
    status: ImportStatus
    book_file: Optional[BookFile] = None
    book: Optional[Book] = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    checksum: Optional[str] = None


_FILENAME_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9 .,_()\\-]+")
_FILENAME_SPACES_RE = re.compile(r"\\s+")
SHA256_CHUNK_BYTES = 1024 * 1024


def _sanitize_filename_component(value: str) -> str:
    value = (value or "").strip()
    value = _FILENAME_SAFE_CHARS_RE.sub("_", value)
    value = _FILENAME_SPACES_RE.sub(" ", value).strip()
    value = value.strip(" .")
    return value or "Unknown"


def generate_epub_download_filename(*, book: Book) -> str:
    author = (
        book.authors.order_by("name").values_list("name", flat=True).first()
        or "Unknown Author"
    )
    parts: list[str] = [_sanitize_filename_component(author)]

    if book.series is not None:
        series_name = _sanitize_filename_component(book.series.name)
        if book.series_index is not None:
            parts.append(f"{series_name} {book.series_index}")
        else:
            parts.append(series_name)

    parts.append(_sanitize_filename_component(book.title))
    filename = " - ".join(parts)
    return f"{filename}.epub"


def calculate_file_sha256(file_obj, *, chunk_size: int = SHA256_CHUNK_BYTES) -> tuple[str, int]:
    digest = hashlib.sha256()
    total_size = 0
    seek = getattr(file_obj, "seek", None)
    if callable(seek):
        seek(0)

    chunks = getattr(file_obj, "chunks", None)
    if callable(chunks):
        iterator = chunks(chunk_size=chunk_size)
    else:
        iterator = iter(lambda: file_obj.read(chunk_size), b"")

    for chunk in iterator:
        if not chunk:
            continue
        digest.update(chunk)
        total_size += len(chunk)

    if callable(seek):
        seek(0)

    return digest.hexdigest(), total_size


def _clean_str(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _normalize_language(value: str) -> str:
    return value.strip().lower()


def _dedupe_nonblank(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        v = _clean_str(raw)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _looks_like_doi(value: str) -> bool:
    v = value.strip()
    if v.lower().startswith("doi:"):
        v = v[4:].strip()
    return v.startswith("10.") and "/" in v


def _parse_isbn(value: str) -> tuple[str, str] | None:
    raw = value.strip()
    if not raw:
        return None

    lowered = raw.lower()
    if lowered.startswith("urn:isbn:"):
        raw = raw.split(":", 2)[-1]
    if lowered.startswith("isbn:"):
        raw = raw.split(":", 1)[-1]

    cleaned = re.sub(r"[^0-9xX]", "", raw)
    if len(cleaned) == 13 and cleaned.isdigit():
        return (BookIdentifier.SCHEME_ISBN_13, cleaned)
    if len(cleaned) == 10 and re.fullmatch(r"[0-9]{9}[0-9xX]", cleaned):
        return (BookIdentifier.SCHEME_ISBN_10, cleaned.upper())
    return None


def _identifier_scheme_for(*, value: str, attrs: dict[str, Any]) -> str:
    v = value.strip()
    v_lower = v.lower()

    isbn = _parse_isbn(v)
    if isbn is not None:
        return isbn[0]

    if _looks_like_doi(v):
        return BookIdentifier.SCHEME_DOI

    if v_lower.startswith(("http://", "https://", "urn:")):
        if v_lower.startswith("urn:uuid:"):
            return BookIdentifier.SCHEME_UUID
        return BookIdentifier.SCHEME_URI

    if _UUID_RE.match(v):
        return BookIdentifier.SCHEME_UUID

    hinted = any(
        "asin" in str(attrs.get(k, "")).lower() for k in ("scheme", "type", "id")
    ) or v_lower.startswith(("asin:", "urn:asin:"))
    if hinted and re.fullmatch(r"[A-Z0-9]{10}", v.upper()):
        return BookIdentifier.SCHEME_ASIN

    return BookIdentifier.SCHEME_OTHER


def _normalize_identifier_value(*, scheme: str, value: str) -> str:
    v = value.strip()
    if scheme in {BookIdentifier.SCHEME_ISBN_10, BookIdentifier.SCHEME_ISBN_13}:
        parsed = _parse_isbn(v)
        if parsed is not None:
            return parsed[1]
    if scheme == BookIdentifier.SCHEME_DOI and v.lower().startswith("doi:"):
        return v[4:].strip()
    if scheme == BookIdentifier.SCHEME_ASIN and v.lower().startswith("asin:"):
        return v.split(":", 1)[-1].strip().upper()
    return v


def _extract_identifiers(book_epub) -> list[dict[str, Any]]:
    identifiers: list[dict[str, Any]] = []
    raw_identifiers = book_epub.get_metadata("DC", "identifier") or []
    for raw_value, raw_attrs in raw_identifiers:
        value = _clean_str(raw_value)
        if not value:
            continue
        attrs = raw_attrs or {}
        scheme = _identifier_scheme_for(value=value, attrs=attrs)
        normalized_value = _normalize_identifier_value(scheme=scheme, value=value)
        if not normalized_value:
            continue
        identifiers.append(
            {
                "scheme": scheme,
                "value": normalized_value,
                "source": "epub",
                "is_primary": False,
            }
        )

    primary_index: int | None = None
    for idx, ident in enumerate(identifiers):
        if ident["scheme"] == BookIdentifier.SCHEME_ISBN_13:
            primary_index = idx
            break
    if primary_index is None:
        for idx, ident in enumerate(identifiers):
            if ident["scheme"] == BookIdentifier.SCHEME_ISBN_10:
                primary_index = idx
                break
    if primary_index is None and identifiers:
        primary_index = 0
    if primary_index is not None:
        identifiers[primary_index]["is_primary"] = True

    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for ident in identifiers:
        key = (ident["scheme"], ident["value"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(ident)
    return out


def _best_isbn_from_identifiers(identifiers: list[dict[str, Any]]) -> str:
    isbn13 = next(
        (i["value"] for i in identifiers if i["scheme"] == BookIdentifier.SCHEME_ISBN_13),
        "",
    )
    if isbn13:
        return isbn13
    isbn10 = next(
        (i["value"] for i in identifiers if i["scheme"] == BookIdentifier.SCHEME_ISBN_10),
        "",
    )
    return isbn10 or ""


def _parse_series_index(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    if d < 0:
        return None
    try:
        normalized = d.quantize(Decimal("0.1"))
    except Exception:
        return None
    exp = int(d.as_tuple().exponent)
    if exp < -1:
        return None
    return normalized


def _extract_metadata(book_epub):
    metadata: dict[str, Any] = {}

    titles = book_epub.get_metadata("DC", "title") or []
    title_values = _dedupe_nonblank([t[0] for t in titles if t and t[0]])
    if title_values:
        metadata["title"] = title_values[0]
        if len(title_values) > 1:
            subtitle = title_values[1]
            if subtitle and subtitle != title_values[0]:
                metadata["subtitle"] = subtitle

    creators = book_epub.get_metadata("DC", "creator") or []
    metadata["authors"] = _dedupe_nonblank([c[0] for c in creators if c and c[0]])

    language = book_epub.get_metadata("DC", "language") or []
    if language and language[0] and language[0][0]:
        lang = _clean_str(language[0][0])
        if lang:
            metadata["language"] = _normalize_language(lang)

    publisher = book_epub.get_metadata("DC", "publisher") or []
    if publisher and publisher[0] and publisher[0][0]:
        pub = _clean_str(publisher[0][0])
        if pub:
            metadata["publisher"] = pub

    description = book_epub.get_metadata("DC", "description") or []
    if description and description[0] and description[0][0]:
        desc = _clean_str(description[0][0])
        if desc:
            metadata["summary"] = desc

    subjects = book_epub.get_metadata("DC", "subject") or []
    metadata["subjects"] = _dedupe_nonblank([s[0] for s in subjects if s and s[0]])

    date = book_epub.get_metadata("DC", "date") or []
    if date and date[0] and date[0][0]:
        raw_date = _clean_str(date[0][0])
        if len(raw_date) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date[:10]):
            metadata["published_date"] = raw_date[:10]

    identifiers = _extract_identifiers(book_epub)
    metadata["identifiers"] = identifiers
    metadata["isbn"] = _best_isbn_from_identifiers(identifiers)

    return metadata


def import_epub_impl(
    *,
    epub_module,
    file_path: str,
    sidecar_opf_bytes: bytes | None = None,
    sidecar_opf_dir: str | None = None,
    sidecar_asset_reader: Callable[[str], bytes | None] | None = None,
) -> ImportResult:
    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"File does not exist: {file_path}")
    if path.suffix.lower() != ".epub":
        raise ValueError(f"File must have .epub extension: {file_path}")

    with open(path, "rb") as f:
        checksum, file_size = calculate_file_sha256(f)

    existing = BookFile.objects.filter(checksum=checksum).first()
    if existing:
        return ImportResult(
            status=ImportStatus.DUPLICATE,
            book_file=existing,
            book=existing.book,
            checksum=checksum,
            message="EPUB already exists.",
        )

    book_epub = epub_module.read_epub(str(path))
    epub_metadata = _extract_metadata(book_epub)

    sidecar_metadata: dict[str, Any] | None = None
    if sidecar_opf_bytes:
        sidecar_metadata = extract_opf_sidecar_metadata(
            opf_xml=sidecar_opf_bytes,
            clean_str=_clean_str,
            dedupe_nonblank=_dedupe_nonblank,
            normalize_language=_normalize_language,
            identifier_scheme_for=_identifier_scheme_for,
            normalize_identifier_value=_normalize_identifier_value,
            best_isbn_from_identifiers=_best_isbn_from_identifiers,
            parse_series_index=_parse_series_index,
            book_identifier_model=BookIdentifier,
        )

    metadata = merge_metadata(
        epub=epub_metadata,
        opf=sidecar_metadata,
        clean_str=_clean_str,
        best_isbn_from_identifiers=_best_isbn_from_identifiers,
    )

    raw_series_index = metadata.get("series_index")
    if raw_series_index is not None and raw_series_index != "":
        metadata["series_index"] = _parse_series_index(raw_series_index)

    def cover_hook(book: Book) -> None:
        if sidecar_opf_bytes and sidecar_opf_dir and sidecar_asset_reader:
            try:
                try_set_book_cover_from_sidecar_opf(
                    book=book,
                    opf_xml=sidecar_opf_bytes,
                    opf_dir=sidecar_opf_dir,
                    asset_reader=sidecar_asset_reader,
                )
            except Exception:
                pass

        if not getattr(book, "cover_file", None):
            try:
                extract_epub_embedded_cover_to_book(book=book, epub_path=str(path), save=True)
            except Exception:
                pass

    book, book_file = persist_new_imported_book(
        metadata=metadata,
        source_path=path,
        checksum=checksum,
        file_size=file_size,
        added_by=None,
        cover_hook=cover_hook,
    )

    return ImportResult(
        status=ImportStatus.IMPORTED,
        book_file=book_file,
        book=book,
        checksum=checksum,
        message="Successfully imported EPUB.",
    )


def import_epub(
    file_path: str,
    *,
    sidecar_opf_bytes: bytes | None = None,
    sidecar_opf_dir: str | None = None,
    sidecar_asset_reader=None,
) -> ImportResult:
    return import_epub_impl(
        epub_module=epub,
        file_path=file_path,
        sidecar_opf_bytes=sidecar_opf_bytes,
        sidecar_opf_dir=sidecar_opf_dir,
        sidecar_asset_reader=sidecar_asset_reader,
    )
