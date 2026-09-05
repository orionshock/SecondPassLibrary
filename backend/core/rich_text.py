from __future__ import annotations

import nh3
from django.core.exceptions import ValidationError


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
DESCRIPTIVE_PROSE_MAX_LENGTH = 25_000

_LIMITED_RICH_TEXT_CLEANER = nh3.Cleaner(
    tags=LIMITED_RICH_TEXT_TAGS,
    clean_content_tags=LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS,
    attributes={},
    link_rel=None,
)


def sanitize_limited_html(value: str | None) -> str:
    """Return the canonical server-sanitized limited HTML fragment."""
    return _LIMITED_RICH_TEXT_CLEANER.clean(str(value or ""))


def sanitize_descriptive_prose(
    value: str | None,
    *,
    field_name: str | None = None,
) -> str:
    """Sanitize descriptive prose and enforce its stored-HTML size contract."""
    sanitized = sanitize_limited_html(value)
    if len(sanitized) <= DESCRIPTIVE_PROSE_MAX_LENGTH:
        return sanitized

    message = (
        "Ensure the sanitized HTML has at most "
        f"{DESCRIPTIVE_PROSE_MAX_LENGTH:,} characters."
    )
    if field_name is not None:
        raise ValidationError({field_name: message})
    raise ValidationError(message)
