from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from library.imports.normalization import normalize_identifier
from library.models import Author, Book, BookAuthor, BookIdentifier, BookSeries, Series


@transaction.atomic
def update_book_metadata(
    *,
    book: Book,
    scalar_fields: dict,
    authors: list[Author] | None = None,
    series: Series | dict | None = None,
    series_supplied: bool = False,
    series_index=None,
    series_index_supplied: bool = False,
    identifiers: list[dict] | None = None,
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

    if isinstance(series, dict):
        series_name = series["name"]
        series = Series.objects.filter(name__iexact=series_name).order_by("id").first()
        if series is None:
            series = Series.objects.create(name=series_name)

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

    if identifiers is not None:
        normalized_identifiers = []
        keys = set()
        for item in identifiers:
            normalized = normalize_identifier(scheme=item["scheme"], value=item["value"])
            if normalized is None:
                raise ValidationError({"identifiers": "Identifier value is required."})
            key = (normalized.scheme, normalized.normalized_value)
            if key in keys:
                raise ValidationError({"identifiers": "Duplicate identifiers are not allowed."})
            keys.add(key)
            if (
                BookIdentifier.objects.filter(
                    scheme=normalized.scheme,
                    normalized_value=normalized.normalized_value,
                )
                .exclude(book=book)
                .exists()
            ):
                raise ValidationError({"identifiers": "An identifier already belongs to another book."})
            normalized_identifiers.append(normalized)

        BookIdentifier.objects.filter(book=book).delete()
        BookIdentifier.objects.bulk_create(
            [
                BookIdentifier(
                    book=book,
                    scheme=item.scheme,
                    value=item.value,
                    normalized_value=item.normalized_value,
                )
                for item in normalized_identifiers
            ]
        )

    return book
