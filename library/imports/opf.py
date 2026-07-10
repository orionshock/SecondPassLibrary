from __future__ import annotations

from collections.abc import Iterable

from defusedxml import ElementTree

from library.imports.normalization import (
    build_import_tags,
    collapse_whitespace,
    fallback_sort_value,
    normalize_identifier,
    parse_partial_date,
    parse_series_index,
)
from library.imports.dto import ImportAuthor, ImportIdentifier, ImportMetadata, ImportSeries


def parse_opf_metadata(opf_xml: str | bytes) -> ImportMetadata:
    root = ElementTree.fromstring(opf_xml)
    metadata = _first_child(root, "metadata")
    if metadata is None:
        metadata = root
    title = _first_text(metadata, "title") or "Untitled"
    sort_title = fallback_sort_value(
        value=title,
        explicit_sort=_first_meta_content(metadata, "calibre:title_sort", "title_sort"),
    )
    published_year, published_month, published_day, precision = parse_partial_date(
        _first_text(metadata, "date")
    )
    return ImportMetadata(
        title=collapse_whitespace(title),
        sort_title=sort_title,
        subtitle=_first_meta_content(metadata, "calibre:subtitle", "subtitle") or "",
        authors=_parse_authors(metadata),
        series=_parse_series(metadata),
        language=_first_text(metadata, "language") or "",
        publisher=_first_text(metadata, "publisher") or "",
        description=_first_text(metadata, "description") or "",
        published_year=published_year,
        published_month=published_month,
        published_day=published_day,
        published_date_precision=precision,
        tags=build_import_tags(_texts(metadata, "subject") + _calibre_tags(metadata)),
        identifiers=_parse_identifiers(metadata),
    )


def _parse_authors(metadata: ElementTree.Element) -> list[ImportAuthor]:
    author_sort = _first_meta_content(metadata, "calibre:author_sort", "author_sort")
    authors: list[ImportAuthor] = []
    for position, creator in enumerate(_children(metadata, "creator")):
        name = collapse_whitespace(creator.text)
        if not name:
            continue
        sort_name = _file_as(creator) or (author_sort if position == 0 else "")
        authors.append(
            ImportAuthor(
                name=name,
                sort_name=fallback_sort_value(value=name, explicit_sort=sort_name),
                position=len(authors),
            )
        )
    return authors


def _parse_series(metadata: ElementTree.Element) -> ImportSeries | None:
    name = _first_meta_content(metadata, "calibre:series", "series")
    if not name:
        return None
    sort_name = _first_meta_content(metadata, "calibre:series_sort", "series_sort")
    return ImportSeries(
        name=name,
        sort_name=fallback_sort_value(value=name, explicit_sort=sort_name),
        series_index=parse_series_index(
            _first_meta_content(metadata, "calibre:series_index", "series_index")
        ),
    )


def _parse_identifiers(metadata: ElementTree.Element) -> list[ImportIdentifier]:
    identifiers = []
    seen = set()
    for item in _children(metadata, "identifier"):
        value = collapse_whitespace(item.text)
        scheme = item.attrib.get("{http://www.idpf.org/2007/opf}scheme") or item.attrib.get("scheme")
        identifier = normalize_identifier(scheme=scheme or "epub_uid", value=value)
        if identifier is None:
            continue
        key = (identifier.scheme, identifier.normalized_value)
        if key in seen:
            continue
        seen.add(key)
        identifiers.append(identifier)
    return identifiers


def _calibre_tags(metadata: ElementTree.Element) -> list[str]:
    values: list[str] = []
    for item in _meta_elements(metadata):
        if item.attrib.get("name") != "calibre:tags":
            continue
        content = item.attrib.get("content", "")
        values.extend(part.strip() for part in content.split(","))
    return values


def _file_as(creator: ElementTree.Element) -> str:
    value = creator.attrib.get("{http://www.idpf.org/2007/opf}file-as")
    return collapse_whitespace(value)


def _first_text(parent: ElementTree.Element, local_name: str) -> str:
    for child in _children(parent, local_name):
        value = collapse_whitespace(child.text)
        if value:
            return value
    return ""


def _texts(parent: ElementTree.Element, local_name: str) -> list[str]:
    return [value for value in (collapse_whitespace(child.text) for child in _children(parent, local_name)) if value]


def _first_meta_content(parent: ElementTree.Element, *names: str) -> str:
    wanted = set(names)
    for item in _meta_elements(parent):
        if item.attrib.get("name") in wanted or item.attrib.get("property") in wanted:
            value = collapse_whitespace(item.attrib.get("content") or item.text)
            if value:
                return value
    return ""


def _meta_elements(parent: ElementTree.Element) -> Iterable[ElementTree.Element]:
    return _children(parent, "meta")


def _first_child(parent: ElementTree.Element, local_name: str) -> ElementTree.Element | None:
    for child in _children(parent, local_name):
        return child
    return None


def _children(parent: ElementTree.Element, local_name: str) -> Iterable[ElementTree.Element]:
    for child in parent.iter():
        if _local_name(child.tag) == local_name:
            yield child


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
