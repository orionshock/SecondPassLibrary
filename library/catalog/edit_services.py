from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from library.imports.normalization import normalize_identifier
from library.models import Author, Book, BookAuthor, BookIdentifier, BookSeries, Series


@transaction.atomic
def update_book_metadata(
    *,
    book: Book,
    scalar_fields: dict,
    authors: list[Author] | None = None,
    series: Series | None = None,
    series_supplied: bool = False,
    series_index=None,
    series_index_supplied: bool = False,
) -> Book:
    for field, value in scalar_fields.items():
        setattr(book, field, value)
    book.full_clean()
    if scalar_fields:
        book.save(update_fields=[*scalar_fields, "updated_at"])

    if authors is not None:
        BookAuthor.objects.filter(book=book).delete()
        BookAuthor.objects.bulk_create(
            [BookAuthor(book=book, author=author, position=position) for position, author in enumerate(authors)]
        )

    existing_link = BookSeries.objects.filter(book=book).first()
    target_series = series if series_supplied else (existing_link.series if existing_link else None)
    target_index = series_index if series_index_supplied else (existing_link.series_index if existing_link else None)
    if target_series is None:
        if series_supplied and existing_link is not None:
            existing_link.delete()
    else:
        BookSeries.objects.update_or_create(
            book=book,
            defaults={"series": target_series, "series_index": target_index},
        )

    return book


def create_book_identifier(*, book: Book, scheme: str, value: str) -> BookIdentifier:
    normalized = normalize_identifier(scheme=scheme, value=value)
    if normalized is None:
        raise ValidationError({"value": "Identifier value is required."})
    try:
        return BookIdentifier.objects.create(
            book=book,
            scheme=normalized.scheme,
            value=normalized.value,
            normalized_value=normalized.normalized_value,
        )
    except IntegrityError as exc:
        raise ValidationError({"value": "This identifier already exists."}) from exc


def update_book_identifier(*, identifier: BookIdentifier, scheme: str, value: str) -> BookIdentifier:
    normalized = normalize_identifier(scheme=scheme, value=value)
    if normalized is None:
        raise ValidationError({"value": "Identifier value is required."})
    identifier.scheme = normalized.scheme
    identifier.value = normalized.value
    identifier.normalized_value = normalized.normalized_value
    try:
        identifier.save(update_fields=["scheme", "value", "normalized_value", "updated_at"])
    except IntegrityError as exc:
        raise ValidationError({"value": "This identifier already exists."}) from exc
    return identifier
