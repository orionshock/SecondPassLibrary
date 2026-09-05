from __future__ import annotations

import nh3


LIMITED_RICH_TEXT_TAGS = {
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
LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS = {"script", "style"}

_LIMITED_RICH_TEXT_CLEANER = nh3.Cleaner(
    tags=LIMITED_RICH_TEXT_TAGS,
    clean_content_tags=LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS,
    attributes={},
    link_rel=None,
)


def sanitize_limited_html(value: str | None) -> str:
    """Return the canonical server-sanitized limited HTML fragment."""
    return _LIMITED_RICH_TEXT_CLEANER.clean(str(value or ""))
