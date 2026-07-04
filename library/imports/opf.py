from __future__ import annotations

from decimal import Decimal
import posixpath
import re
from typing import Any, Callable, cast

from defusedxml import ElementTree as SafeElementTree

from ..cover_services import find_cover_href_in_opf, set_book_cover_from_bytes, MAX_COVER_BYTES
from ..models import Book


MAX_OPF_SIDECAR_XML_BYTES = 1024 * 1024


def extract_opf_sidecar_metadata(
    *,
    opf_xml: bytes,
    clean_str: Callable[[object], str],
    dedupe_nonblank: Callable[[list[str]], list[str]],
    normalize_language: Callable[[str], str],
    identifier_scheme_for: Callable[..., str],
    normalize_identifier_value: Callable[..., str],
    best_isbn_from_identifiers: Callable[[list[dict[str, Any]]], str],
    parse_series_index: Callable[[object], Decimal | None],
    book_identifier_model,
) -> dict[str, Any] | None:
    if not opf_xml or len(opf_xml) > MAX_OPF_SIDECAR_XML_BYTES:
        return None
    try:
        root = SafeElementTree.fromstring(opf_xml)
    except Exception:
        return None

    dc_ns = "http://purl.org/dc/elements/1.1/"
    out: dict[str, Any] = {}

    def dc_texts(local_name: str) -> list[str]:
        vals: list[str] = []
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            if not el.tag.endswith("}" + local_name):
                continue
            if not el.tag.startswith("{" + dc_ns + "}"):
                continue
            text = clean_str(el.text)
            if text:
                vals.append(text)
        return dedupe_nonblank(vals)

    titles = dc_texts("title")
    if titles:
        out["title"] = titles[0]

    creators = dc_texts("creator")
    if creators:
        out["authors"] = creators

    publishers = dc_texts("publisher")
    if publishers:
        out["publisher"] = publishers[0]

    languages = dc_texts("language")
    if languages:
        out["language"] = normalize_language(languages[0])

    descriptions = dc_texts("description")
    if descriptions:
        out["summary"] = descriptions[0]

    subjects = dc_texts("subject")
    if subjects:
        out["subjects"] = subjects

    dates = dc_texts("date")
    if dates:
        raw_date = dates[0]
        if len(raw_date) >= 10 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date[:10]):
            out["published_date"] = raw_date[:10]

    series_name: str = ""
    series_index_raw: object | None = None
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.tag.endswith("meta"):
            continue
        name = clean_str(el.attrib.get("name", "")).lower()
        content = clean_str(el.attrib.get("content", ""))
        if name == "calibre:series" and content:
            series_name = content
        elif name == "calibre:series_index" and content:
            series_index_raw = content
    if series_name:
        out["series_name"] = series_name
    if series_index_raw is not None:
        parsed = parse_series_index(series_index_raw)
        if parsed is not None:
            out["series_index"] = parsed

    identifiers: list[dict[str, Any]] = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if not el.tag.startswith("{" + dc_ns + "}") or not el.tag.endswith("}identifier"):
            continue
        value = clean_str(el.text)
        if not value:
            continue
        attrs = dict(el.attrib or {})
        scheme = identifier_scheme_for(value=value, attrs=attrs)
        normalized_value = normalize_identifier_value(scheme=scheme, value=value)
        if not normalized_value:
            continue
        identifiers.append(
            {
                "scheme": scheme,
                "value": normalized_value,
                "source": "opf_sidecar",
                "is_primary": False,
            }
        )

    primary_index: int | None = None
    for idx, ident in enumerate(identifiers):
        if ident["scheme"] == book_identifier_model.SCHEME_ISBN_13:
            primary_index = idx
            break
    if primary_index is None:
        for idx, ident in enumerate(identifiers):
            if ident["scheme"] == book_identifier_model.SCHEME_ISBN_10:
                primary_index = idx
                break
    if primary_index is None and identifiers:
        primary_index = 0
    if primary_index is not None:
        identifiers[primary_index]["is_primary"] = True

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for ident in identifiers:
        key = (str(ident["scheme"]), str(ident["value"]).lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ident)

    if deduped:
        out["identifiers"] = deduped
        out["isbn"] = best_isbn_from_identifiers(deduped)

    return out


def merge_metadata(*, epub: dict[str, Any], opf: dict[str, Any] | None, clean_str: Callable[[object], str], best_isbn_from_identifiers: Callable[[list[dict[str, Any]]], str]) -> dict[str, Any]:
    if not opf:
        return epub

    merged: dict[str, Any] = dict(epub)

    def take_str(key: str):
        v = clean_str(opf.get(key, ""))
        if v:
            merged[key] = v

    def take_list(key: str):
        v = opf.get(key)
        if isinstance(v, list) and v:
            merged[key] = v

    take_str("title")
    take_str("publisher")
    take_str("language")
    take_str("summary")
    if opf.get("published_date"):
        merged["published_date"] = opf.get("published_date")
    take_list("authors")
    take_list("subjects")
    if isinstance(opf.get("identifiers"), list) and opf.get("identifiers"):
        merged["identifiers"] = opf.get("identifiers")
        merged["isbn"] = best_isbn_from_identifiers(cast(list[dict[str, Any]], merged["identifiers"]))
    if clean_str(opf.get("series_name", "")):
        merged["series_name"] = clean_str(opf.get("series_name", ""))
    if opf.get("series_index") is not None:
        merged["series_index"] = opf.get("series_index")

    return merged


def try_set_book_cover_from_sidecar_opf(
    *,
    book: Book,
    opf_xml: bytes,
    opf_dir: str,
    asset_reader: Callable[[str], bytes | None],
) -> bool:
    if getattr(book, "cover_file", None):
        return False

    try:
        href = find_cover_href_in_opf(opf_xml=opf_xml)
        if not href:
            return False
        cover_member = posixpath.normpath(posixpath.join(opf_dir, href))
        if cover_member.startswith("../") or cover_member.startswith("/") or cover_member == "..":
            return False
        data = asset_reader(cover_member)
        if not data:
            return False
        if len(data) > MAX_COVER_BYTES:
            return False
        set_book_cover_from_bytes(
            book=book,
            data=data,
            source="opf_sidecar",
            source_filename=posixpath.basename(cover_member) or None,
            save=True,
        )
        return True
    except Exception:
        return False
