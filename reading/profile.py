from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CURRENT_READING_PROFILE_VERSION = "0.1.0"
CURRENT_READING_PROFILE_ID = (
    "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0"
)
EPUB_CFI_CONFORMS_TO = "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"


def normalize_epub_cfi(value: object) -> str:
    if value is None or not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("epubcfi("):
        return raw
    return f"epubcfi({raw})"


def _ensure_mapping(value: object, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object.")
    return dict(value)


def validate_profile_version(value: object) -> str:
    if value is None or value == "":
        return CURRENT_READING_PROFILE_VERSION
    if not isinstance(value, str):
        raise ValueError("profile_version must be a string.")
    if value != CURRENT_READING_PROFILE_VERSION:
        raise ValueError(
            f"Unsupported profile_version '{value}'. Expected '{CURRENT_READING_PROFILE_VERSION}'."
        )
    return value


def validate_fragment_selector(selector: object) -> dict[str, Any]:
    selector_dict = _ensure_mapping(selector, field="selector")
    if not selector_dict:
        return {}

    allowed_selector_keys = {"type", "conformsTo", "value", "updated"}
    unknown = set(selector_dict.keys()).difference(allowed_selector_keys)
    if unknown:
        raise ValueError(f"Unsupported selector fields: {', '.join(sorted(unknown))}.")

    selector_type = selector_dict.get("type")
    if selector_type is not None and selector_type != "FragmentSelector":
        raise ValueError("selector.type must be 'FragmentSelector' when provided.")

    conforms_to = selector_dict.get("conformsTo")
    if conforms_to is not None and conforms_to != EPUB_CFI_CONFORMS_TO:
        raise ValueError(f"selector.conformsTo must be '{EPUB_CFI_CONFORMS_TO}'.")

    value = selector_dict.get("value")
    if value is not None:
        normalized = normalize_epub_cfi(value)
        if not normalized:
            raise ValueError("selector.value must be a non-empty string when provided.")
        selector_dict["value"] = normalized

    return selector_dict


def validate_current_location(current_location: object) -> dict[str, Any]:
    loc = _ensure_mapping(current_location, field="current_location")
    if not loc:
        return {}

    allowed_keys = {"format", "source", "selector", "updated", "cfi", "href", "position", "text"}
    unknown = set(loc.keys()).difference(allowed_keys)
    if unknown:
        raise ValueError(
            f"Unsupported current_location fields: {', '.join(sorted(unknown))}."
        )

    fmt = loc.get("format")
    if fmt is not None and fmt != "epub":
        raise ValueError("current_location.format must be 'epub' when provided.")
    if fmt is None:
        loc["format"] = "epub"

    if "source" in loc:
        src = loc.get("source")
        if src is None:
            loc["source"] = {}
        else:
            loc["source"] = _ensure_mapping(src, field="current_location.source")

    if "selector" in loc:
        loc["selector"] = validate_fragment_selector(loc.get("selector"))

    # Allow shorthand `cfi` and normalize into a FragmentSelector when `selector`
    # is missing. Do not over-validate the actual CFI string.
    if "cfi" in loc and (not loc.get("selector")):
        loc["selector"] = {
            "type": "FragmentSelector",
            "conformsTo": EPUB_CFI_CONFORMS_TO,
            "value": normalize_epub_cfi(loc.get("cfi")),
        }

    return loc


def validate_annotation_target(target: object) -> dict[str, Any]:
    target_dict = _ensure_mapping(target, field="target")
    if not target_dict:
        return {}

    allowed_target_keys = {"source", "selector"}
    unknown = set(target_dict.keys()).difference(allowed_target_keys)
    if unknown:
        raise ValueError(f"Unsupported target fields: {', '.join(sorted(unknown))}.")

    if "source" in target_dict:
        source = target_dict.get("source")
        source_dict = _ensure_mapping(source, field="target.source")
        allowed_source_keys = {
            "id",
            "type",
            "book_id",
            "book_file_id",
            "checksum",
            "fileHash",
            "title",
            "authors",
            "author",
            "identifiers",
            "media_type",
        }
        unknown_source = set(source_dict.keys()).difference(allowed_source_keys)
        if unknown_source:
            raise ValueError(
                f"Unsupported target.source fields: {', '.join(sorted(unknown_source))}."
            )
        target_dict["source"] = source_dict

    if "selector" in target_dict:
        target_dict["selector"] = validate_fragment_selector(target_dict.get("selector"))

    return target_dict


def validate_annotation_body(body: object) -> list[dict[str, Any]]:
    if body is None:
        return []

    bodies: list[dict[str, Any]]
    if isinstance(body, Mapping):
        bodies = [dict(body)]
    elif isinstance(body, list):
        bodies = []
        for idx, item in enumerate(body):
            if not isinstance(item, Mapping):
                raise ValueError(f"body[{idx}] must be an object.")
            bodies.append(dict(item))
    else:
        raise ValueError("body must be an object or a list of objects.")

    allowed_body_keys = {"type", "value", "purpose", "format", "language", "color"}
    for idx, body_dict in enumerate(bodies):
        unknown = set(body_dict.keys()).difference(allowed_body_keys)
        if unknown:
            raise ValueError(
                f"Unsupported body fields in body[{idx}]: {', '.join(sorted(unknown))}."
            )
    return bodies
