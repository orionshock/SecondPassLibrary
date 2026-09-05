from __future__ import annotations

from django.db import transaction
from django.db.models.deletion import ProtectedError

from core.rich_text import sanitize_limited_html
from library.catalog.names import normalize_catalog_entity_name
from library.models import Author, BookAuthor, BookSeries, Series


class CatalogEntityInUseError(Exception):
    def __init__(self, *, code: str, message: str, attached_book_count: int):
        self.code = code
        self.attached_book_count = attached_book_count
        super().__init__(message)


def _entity_in_use_error(
    *, kind: str, code: str, attached_book_count: int
) -> CatalogEntityInUseError:
    return CatalogEntityInUseError(
        code=code,
        message=(
            f"{kind} cannot be deleted because {attached_book_count} "
            f"{'Book is' if attached_book_count == 1 else 'Books are'} attached."
        ),
        attached_book_count=attached_book_count,
    )


def create_author(*, name: str, sort_name: str = "", biography: str = "") -> Author:
    author = Author(
        name=name,
        sort_name=sort_name or name,
        normalized_name=normalize_catalog_entity_name(name),
        biography=sanitize_limited_html(biography),
    )
    author.full_clean()
    author.save()
    return author


def update_author(*, author: Author, fields: dict) -> Author:
    if not fields:
        return author
    fields = dict(fields)
    if "biography" in fields:
        fields["biography"] = sanitize_limited_html(fields["biography"])
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
    fields = dict(fields)
    if "summary" in fields:
        fields["summary"] = sanitize_limited_html(fields["summary"])
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
        summary=sanitize_limited_html(summary),
    )
    series.full_clean()
    series.save()
    return series


@transaction.atomic
def delete_author(*, author: Author) -> None:
    author = Author.objects.select_for_update().get(pk=author.pk)
    attached_book_count = BookAuthor.objects.filter(author=author).count()
    if attached_book_count:
        raise _entity_in_use_error(
            kind="Author", code="author_has_books", attached_book_count=attached_book_count
        )
    try:
        author.delete()
    except ProtectedError as exc:
        attached_book_count = max(
            BookAuthor.objects.filter(author=author).count(), len(exc.protected_objects), 1
        )
        raise _entity_in_use_error(
            kind="Author", code="author_has_books", attached_book_count=attached_book_count
        ) from exc


@transaction.atomic
def delete_series(*, series: Series) -> None:
    series = Series.objects.select_for_update().get(pk=series.pk)
    attached_book_count = BookSeries.objects.filter(series=series).count()
    if attached_book_count:
        raise _entity_in_use_error(
            kind="Series", code="series_has_books", attached_book_count=attached_book_count
        )
    try:
        series.delete()
    except ProtectedError as exc:
        attached_book_count = max(
            BookSeries.objects.filter(series=series).count(), len(exc.protected_objects), 1
        )
        raise _entity_in_use_error(
            kind="Series", code="series_has_books", attached_book_count=attached_book_count
        ) from exc
