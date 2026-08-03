from __future__ import annotations

from django.db.models import Count, F, Q, QuerySet, Value
from django.db.models.functions import Coalesce, NullIf
from rest_framework.exceptions import ValidationError

from library.catalog.names import normalize_catalog_entity_name
from library.models import Author, Book, CatalogTag, Series


AXIS_ORDERING_AXES = {"name", "book_count"}
AXIS_ORDERINGS = AXIS_ORDERING_AXES | {f"-{axis}" for axis in AXIS_ORDERING_AXES}


def visible_authors_from_books(visible_books: QuerySet[Book]) -> QuerySet[Author]:
    return _with_visible_count(
        Author.objects.filter(book_authors__book__in=visible_books),
        relation="book_authors__book",
        visible_books=visible_books,
    )


def visible_series_from_books(visible_books: QuerySet[Book]) -> QuerySet[Series]:
    return _with_visible_count(
        Series.objects.filter(book_series__book__in=visible_books),
        relation="book_series__book",
        visible_books=visible_books,
    )


def visible_tags_from_books(visible_books: QuerySet[Book]) -> QuerySet[CatalogTag]:
    return _with_visible_count(
        CatalogTag.objects.filter(book_catalog_tags__book__in=visible_books),
        relation="book_catalog_tags__book",
        visible_books=visible_books,
    )


def apply_axis_search(queryset: QuerySet, query_params, *, include_normalized: bool = False) -> QuerySet:
    term = (query_params.get("q") or "").strip()
    if not term:
        return queryset
    condition = Q(name__icontains=term) | Q(sort_name__icontains=term)
    if include_normalized:
        condition |= Q(
            normalized_name__icontains=normalize_catalog_entity_name(term)
        )
    return queryset.filter(condition)


def parse_axis_ordering(request) -> str:
    raw = (request.query_params.get("ordering") or "").strip()
    if not raw:
        return "name"
    if raw not in AXIS_ORDERINGS:
        raise ValidationError(
            {"ordering": f"Invalid ordering. Use one of: {', '.join(sorted(AXIS_ORDERINGS))}."}
        )
    return raw


def apply_axis_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    descending = ordering.startswith("-")
    axis = ordering.removeprefix("-")
    queryset = _with_name_sort(queryset)

    if axis == "name":
        return queryset.order_by(_ordered("_name_sort", descending), _ordered("name", descending), "id")
    if axis == "book_count":
        return queryset.order_by(_ordered("book_count", descending), "_name_sort", "name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


def _with_visible_count(queryset: QuerySet, *, relation: str, visible_books: QuerySet[Book]) -> QuerySet:
    return (
        queryset.annotate(
            book_count=Count(
                relation,
                filter=Q(**{f"{relation}__in": visible_books}),
                distinct=True,
            )
        )
        .filter(book_count__gt=0)
        .distinct()
    )


def _with_name_sort(queryset: QuerySet) -> QuerySet:
    return queryset.annotate(_name_sort=Coalesce(NullIf("sort_name", Value("")), F("name")))


def _ordered(field_name: str, descending: bool):
    expression = F(field_name)
    if descending:
        return expression.desc(nulls_last=True)
    return expression.asc(nulls_last=True)
