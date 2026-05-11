from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from typing import Any


def is_epub_locator(locator: object) -> bool:
    if not isinstance(locator, Mapping):
        return False
    fmt = locator.get("format")
    return fmt in (None, "", "epub")


def normalize_locator(locator: object) -> dict[str, Any]:
    """
    Return a shallow normalized copy of a location/selector dict.

    - Defaults `format` to "epub" if missing/blank.
    - Preserves unknown fields.
    - Does not mutate the input.
    - Does not enforce a strict schema (yet).
    """
    if locator is None:
        return {"format": "epub"}
    if not isinstance(locator, Mapping):
        return {"format": "epub"}

    normalized = dict(copy(dict(locator)))
    fmt = normalized.get("format")
    if fmt is None or (isinstance(fmt, str) and not fmt.strip()):
        normalized["format"] = "epub"
    return normalized


# Canonical naming going forward. Keep `normalize_locator` for now to avoid
# churn while the app migrates to W3C-style `current_location`.
normalize_current_location = normalize_locator
