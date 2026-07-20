from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_catalog_entity_name(value: str) -> str:
    return _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", str(value or "")).strip()
    ).casefold()
