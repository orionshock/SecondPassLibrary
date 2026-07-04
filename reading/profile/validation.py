from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any


CURRENT_READING_PROFILE_VERSION = "0.1.0"
CURRENT_READING_PROFILE_ID = (
    "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0"
)
EPUB_CFI_CONFORMS_TO = "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"

MAX_CURRENT_LOCATION_JSON_BYTES = 16 * 1024

MAX_SELECTOR_VALUE_CHARS = 8 * 1024
MAX_BODY_VALUE_CHARS = 64 * 1024
MAX_SMALL_STRING_CHARS = 255
MAX_TEXT_QUOTE_CONTEXT_CHARS = 500


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


def json_size_bytes(value: object) -> int:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return len(payload.encode("utf-8"))


def validate_json_size(*, value: object, max_bytes: int, field: str) -> None:
    try:
        size = json_size_bytes(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} is not JSON-serializable.") from e
    if size > max_bytes:
        raise ValueError(f"{field} exceeds maximum size ({max_bytes} bytes).")


def _validate_small_string(value: object, *, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    if len(value) > MAX_SMALL_STRING_CHARS:
        raise ValueError(
            f"{field} exceeds maximum length ({MAX_SMALL_STRING_CHARS} chars)."
        )


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
    _validate_small_string(selector_type, field="selector.type")

    conforms_to = selector_dict.get("conformsTo")
    if conforms_to is not None and conforms_to != EPUB_CFI_CONFORMS_TO:
        raise ValueError(f"selector.conformsTo must be '{EPUB_CFI_CONFORMS_TO}'.")
    _validate_small_string(conforms_to, field="selector.conformsTo")

    value = selector_dict.get("value")
    if value is not None:
        normalized = normalize_epub_cfi(value)
        if not normalized:
            raise ValueError("selector.value must be a non-empty string when provided.")
        if len(normalized) > MAX_SELECTOR_VALUE_CHARS:
            raise ValueError(
                f"selector.value exceeds maximum length ({MAX_SELECTOR_VALUE_CHARS} chars)."
            )
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

    validate_json_size(
        value=loc, max_bytes=MAX_CURRENT_LOCATION_JSON_BYTES, field="current_location"
    )
    return loc
