from __future__ import annotations

from library.models import Author, Series


def create_author(*, name: str) -> Author:
    author = Author(name=name, sort_name=name)
    author.full_clean()
    author.save()
    return author


def update_author(*, author: Author, fields: dict) -> Author:
    if not fields:
        return author
    for field, value in fields.items():
        setattr(author, field, value)
    author.full_clean()
    author.save(update_fields=[*fields, "updated_at"])
    return author


def update_series(*, series: Series, fields: dict) -> Series:
    if not fields:
        return series
    for field, value in fields.items():
        setattr(series, field, value)
    series.full_clean()
    series.save(update_fields=[*fields, "updated_at"])
    return series
