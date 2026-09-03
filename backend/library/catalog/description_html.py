from __future__ import annotations

import nh3


BOOK_DESCRIPTION_TAGS = {
    "b",
    "br",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "ul",
}
BOOK_DESCRIPTION_CLEAN_CONTENT_TAGS = {"script", "style"}

_BOOK_DESCRIPTION_CLEANER = nh3.Cleaner(
    tags=BOOK_DESCRIPTION_TAGS,
    clean_content_tags=BOOK_DESCRIPTION_CLEAN_CONTENT_TAGS,
    attributes={},
    link_rel=None,
)


def sanitize_book_description(value: str | None) -> str:
    """Return the canonical safe HTML fragment stored for a Book description."""
    return _BOOK_DESCRIPTION_CLEANER.clean(str(value or ""))
