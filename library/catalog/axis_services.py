from __future__ import annotations

from library.models import Author, Series


def update_author_biography(*, author: Author, biography: str | None) -> Author:
    if biography is None:
        return author
    author.biography = biography
    author.save(update_fields=["biography", "updated_at"])
    return author


def update_series_summary(*, series: Series, summary: str | None) -> Series:
    if summary is None:
        return series
    series.summary = summary
    series.save(update_fields=["summary", "updated_at"])
    return series
