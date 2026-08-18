from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

from library.models import Author, Book, Series


def apply_book_filters(queryset: QuerySet[Book], query_params) -> QuerySet[Book]:
    term = query_params.get("q", "").strip()
    queryset = _apply_title_search(queryset, term)

    author_id = _pk_param(query_params, "author", Author)
    if author_id:
        queryset = queryset.filter(book_authors__author_id=author_id)

    series_id = _pk_param(query_params, "series", Series)
    if series_id:
        queryset = queryset.filter(book_series__series_id=series_id)

    queryset = apply_catalog_tag_filter(queryset, query_params)

    publisher = (query_params.get("publisher") or "").strip()
    if publisher:
        queryset = queryset.filter(publisher__iexact=publisher)

    return queryset.distinct()


def apply_catalog_tag_filter(queryset: QuerySet[Book], query_params) -> QuerySet[Book]:
    slug = (query_params.get("tag") or "").strip()
    if not slug:
        return queryset
    return queryset.filter(book_catalog_tags__catalog_tag__slug=slug).distinct()


def apply_broad_book_search(queryset: QuerySet[Book], term: str) -> QuerySet[Book]:
    if not term:
        return queryset
    return queryset.filter(
        Q(title__icontains=term)
        | Q(sort_title__icontains=term)
        | Q(subtitle__icontains=term)
        | Q(book_authors__author__name__icontains=term)
        | Q(book_series__series__name__icontains=term)
        | Q(identifiers__value__icontains=term)
        | Q(book_catalog_tags__catalog_tag__name__icontains=term)
        | Q(publisher__icontains=term)
        | Q(description__icontains=term)
    ).distinct()


def _apply_title_search(queryset: QuerySet[Book], term: str) -> QuerySet[Book]:
    if not term:
        return queryset
    return queryset.filter(Q(title__icontains=term) | Q(sort_title__icontains=term))


def _pk_param(query_params, name: str, model) -> object | None:
    raw = (query_params.get(name) or "").strip()
    if not raw:
        return None
    try:
        return model._meta.pk.to_python(raw)
    except (DjangoValidationError, ValueError) as exc:
        raise ValidationError({name: "Invalid id."}) from exc
