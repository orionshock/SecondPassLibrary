from __future__ import annotations

from django.db import transaction
from django.db.models.deletion import ProtectedError

from library.catalog.names import normalize_catalog_entity_name
from library.models import Author, BookAuthor, BookSeries, Series


class CatalogEntityInUseError(Exception):
    def __init__(self, *, code: str, message: str):
        self.code = code
        super().__init__(message)


def create_author(*, name: str, sort_name: str = "", biography: str = "") -> Author:
    author = Author(
        name=name,
        sort_name=sort_name or name,
        normalized_name=normalize_catalog_entity_name(name),
        biography=biography,
    )
    author.full_clean()
    author.save()
    return author


def update_author(*, author: Author, fields: dict) -> Author:
    if not fields:
        return author
    for field, value in fields.items():
        setattr(author, field, value)
    if "name" in fields:
        author.normalized_name = normalize_catalog_entity_name(author.name)
        fields = {**fields, "normalized_name": author.normalized_name}
    if "sort_name" in fields and not author.sort_name:
        author.sort_name = author.name
        fields = {**fields, "sort_name": author.sort_name}
    author.full_clean()
    author.save(update_fields=[*fields, "updated_at"])
    return author


def update_series(*, series: Series, fields: dict) -> Series:
    if not fields:
        return series
    for field, value in fields.items():
        setattr(series, field, value)
    if "name" in fields:
        series.normalized_name = normalize_catalog_entity_name(series.name)
        fields = {**fields, "normalized_name": series.normalized_name}
    if "sort_name" in fields and not series.sort_name:
        series.sort_name = series.name
        fields = {**fields, "sort_name": series.sort_name}
    series.full_clean()
    series.save(update_fields=[*fields, "updated_at"])
    return series


def create_series(*, name: str, sort_name: str = "", summary: str = "") -> Series:
    series = Series(
        name=name,
        sort_name=sort_name or name,
        normalized_name=normalize_catalog_entity_name(name),
        summary=summary,
    )
    series.full_clean()
    series.save()
    return series


@transaction.atomic
def delete_author(*, author: Author) -> None:
    if BookAuthor.objects.filter(author=author).exists():
        raise CatalogEntityInUseError(
            code="AUTHOR_IN_USE", message="Author is assigned to one or more books."
        )
    try:
        author.delete()
    except ProtectedError as exc:
        raise CatalogEntityInUseError(
            code="AUTHOR_IN_USE", message="Author is assigned to one or more books."
        ) from exc


@transaction.atomic
def delete_series(*, series: Series) -> None:
    if BookSeries.objects.filter(series=series).exists():
        raise CatalogEntityInUseError(
            code="SERIES_IN_USE", message="Series is assigned to one or more books."
        )
    try:
        series.delete()
    except ProtectedError as exc:
        raise CatalogEntityInUseError(
            code="SERIES_IN_USE", message="Series is assigned to one or more books."
        ) from exc
