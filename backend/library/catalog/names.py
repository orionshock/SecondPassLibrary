from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_catalog_entity_name(value: str) -> str:
    return _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", str(value or "")).strip()
    ).casefold()


class AmbiguousCatalogEntityName(Exception):
    def __init__(
        self,
        *,
        kind: str,
        display_name: str,
        normalized_name: str,
        match_count: int,
        matched_ids: tuple[str, ...],
    ):
        self.kind = kind
        self.display_name = display_name
        self.normalized_name = normalized_name
        self.match_count = match_count
        self.matched_ids = matched_ids
        super().__init__(f"Multiple {kind} records have the same normalized name.")


def find_single_normalized_name_match(*, model, name: str, kind: str):
    normalized_name = normalize_catalog_entity_name(name)
    queryset = model.objects.filter(normalized_name=normalized_name).order_by("id")
    matches = list(queryset[:2])
    if len(matches) > 1:
        raise AmbiguousCatalogEntityName(
            kind=kind,
            display_name=_bounded_name(name),
            normalized_name=_bounded_name(normalized_name),
            match_count=queryset.count(),
            matched_ids=tuple(
                str(identifier)
                for identifier in queryset.values_list("pk", flat=True)[:10]
            ),
        )
    return matches[0] if matches else None


def _bounded_name(value: str, *, max_length: int = 160) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())[:max_length]
