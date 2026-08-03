from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_catalog_entity_name(value: str) -> str:
    return _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", str(value or "")).strip()
    ).casefold()


class AmbiguousCatalogEntityName(Exception):
    def __init__(self, *, kind: str):
        self.kind = kind
        super().__init__(f"Multiple {kind} records have the same normalized name.")


def find_single_normalized_name_match(*, model, name: str, kind: str):
    normalized_name = normalize_catalog_entity_name(name)
    matches = list(
        model.objects.filter(normalized_name=normalized_name).order_by("id")[:2]
    )
    if len(matches) > 1:
        raise AmbiguousCatalogEntityName(kind=kind)
    return matches[0] if matches else None
