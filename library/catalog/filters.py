from __future__ import annotations

from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

from library.models import Author, Book, CatalogTag, Series


def apply_book_filters(queryset: QuerySet[Book], query_params) -> QuerySet[Book]:
    queryset = _apply_search(queryset, query_params.get("q", "").strip())

    author_id = _pk_param(query_params, "author", Author)
    if author_id:
        queryset = queryset.filter(book_authors__author_id=author_id)

    series_id = _pk_param(query_params, "series", Series)
    if series_id:
        queryset = queryset.filter(book_series__series_id=series_id)

    tag_id = _pk_param(query_params, "tag", CatalogTag)
    if tag_id:
        queryset = queryset.filter(book_catalog_tags__catalog_tag_id=tag_id)

    publisher = (query_params.get("publisher") or "").strip()
    if publisher:
        queryset = queryset.filter(publisher__iexact=publisher)

    return queryset.distinct()


def _apply_search(queryset: QuerySet[Book], term: str) -> QuerySet[Book]:
    if not term:
        return queryset
    return queryset.filter(
        Q(title__icontains=term)
        | Q(sort_title__icontains=term)
        | Q(subtitle__icontains=term)
        | Q(description__icontains=term)
        | Q(publisher__icontains=term)
        | Q(book_authors__author__name__icontains=term)
        | Q(book_series__series__name__icontains=term)
        | Q(book_catalog_tags__catalog_tag__name__icontains=term)
        | Q(identifiers__value__icontains=term)
    )


def _pk_param(query_params, name: str, model) -> object | None:
    raw = (query_params.get(name) or "").strip()
    if not raw:
        return None
    try:
        return model._meta.pk.to_python(raw)
    except ValueError as exc:
        raise ValidationError({name: "Invalid id."}) from exc
