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
MAX_TARGET_JSON_BYTES = 16 * 1024
MAX_BODY_JSON_BYTES = 64 * 1024

MAX_SELECTOR_VALUE_CHARS = 8 * 1024
MAX_BODY_VALUE_CHARS = 64 * 1024
MAX_SMALL_STRING_CHARS = 255
MAX_COLOR_CHARS = 64
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


def _validate_optional_color(value: object, *, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    if len(value) > MAX_COLOR_CHARS:
        raise ValueError(f"{field} exceeds maximum length ({MAX_COLOR_CHARS} chars).")

    v = value.strip()
    if v == "":
        return

    allowed = {"yellow", "green", "blue", "pink", "purple", "orange"}
    if v not in allowed:
        raise ValueError(
            f"{field} must be one of: {', '.join(sorted(allowed))}."
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


def validate_text_quote_selector(selector: object) -> dict[str, Any]:
    selector_dict = _ensure_mapping(selector, field="selector")
    if not selector_dict:
        return {}

    allowed_selector_keys = {"type", "exact", "prefix", "suffix"}
    unknown = set(selector_dict.keys()).difference(allowed_selector_keys)
    if unknown:
        raise ValueError(
            f"Unsupported selector fields: {', '.join(sorted(unknown))}."
        )

    selector_type = selector_dict.get("type")
    if selector_type != "TextQuoteSelector":
        raise ValueError("selector.type must be 'TextQuoteSelector'.")

    exact = selector_dict.get("exact")
    if not isinstance(exact, str) or not exact.strip():
        raise ValueError("selector.exact must be a non-empty string.")
    if len(exact) > MAX_BODY_VALUE_CHARS:
        raise ValueError(
            f"selector.exact exceeds maximum length ({MAX_BODY_VALUE_CHARS} chars)."
        )

    prefix = selector_dict.get("prefix")
    if prefix is not None:
        if not isinstance(prefix, str):
            raise ValueError("selector.prefix must be a string.")
        if len(prefix) > MAX_TEXT_QUOTE_CONTEXT_CHARS:
            raise ValueError(
                f"selector.prefix exceeds maximum length ({MAX_TEXT_QUOTE_CONTEXT_CHARS} chars)."
            )

    suffix = selector_dict.get("suffix")
    if suffix is not None:
        if not isinstance(suffix, str):
            raise ValueError("selector.suffix must be a string.")
        if len(suffix) > MAX_TEXT_QUOTE_CONTEXT_CHARS:
            raise ValueError(
                f"selector.suffix exceeds maximum length ({MAX_TEXT_QUOTE_CONTEXT_CHARS} chars)."
            )

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

        for key in ("id", "type", "book_id", "book_file_id", "checksum", "fileHash", "title", "media_type"):
            if key in source_dict:
                _validate_small_string(source_dict.get(key), field=f"target.source.{key}")

        target_dict["source"] = source_dict

    if "selector" in target_dict:
        selector = target_dict.get("selector")
        if isinstance(selector, list):
            fragment: dict[str, Any] | None = None
            quote: dict[str, Any] | None = None
            for idx, raw in enumerate(selector):
                if not isinstance(raw, Mapping):
                    raise ValueError(f"selector[{idx}] must be an object.")
                item = dict(raw)
                stype = item.get("type")
                if stype is None or stype == "FragmentSelector":
                    validated = validate_fragment_selector(item)
                    if validated.get("value") and fragment is None:
                        fragment = validated
                elif stype == "TextQuoteSelector":
                    validated = validate_text_quote_selector(item)
                    if validated and quote is None:
                        quote = validated
                else:
                    raise ValueError(
                        f"Unsupported selector.type: {stype!r}. Expected 'FragmentSelector' or 'TextQuoteSelector'."
                    )

            if fragment is None or not fragment.get("value"):
                raise ValueError(
                    "selector must include a FragmentSelector with a non-empty value."
                )

            selectors_out: list[dict[str, Any]] = [fragment]
            if quote is not None:
                selectors_out.append(quote)
            target_dict["selector"] = selectors_out
        else:
            target_dict["selector"] = validate_fragment_selector(selector)

    validate_json_size(value=target_dict, max_bytes=MAX_TARGET_JSON_BYTES, field="target")
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
        if "type" in body_dict:
            _validate_small_string(body_dict.get("type"), field=f"body[{idx}].type")
        if "purpose" in body_dict:
            _validate_small_string(
                body_dict.get("purpose"), field=f"body[{idx}].purpose"
            )
        if "format" in body_dict:
            _validate_small_string(body_dict.get("format"), field=f"body[{idx}].format")
        if "language" in body_dict:
            _validate_small_string(
                body_dict.get("language"), field=f"body[{idx}].language"
            )
        if "color" in body_dict:
            _validate_optional_color(body_dict.get("color"), field=f"body[{idx}].color")
        if "value" in body_dict:
            value = body_dict.get("value")
            if value is not None and not isinstance(value, str):
                raise ValueError(f"body[{idx}].value must be a string.")
            if isinstance(value, str) and len(value) > MAX_BODY_VALUE_CHARS:
                raise ValueError(
                    f"body[{idx}].value exceeds maximum length ({MAX_BODY_VALUE_CHARS} chars)."
                )

    validate_json_size(value=bodies, max_bytes=MAX_BODY_JSON_BYTES, field="body")
    return bodies
