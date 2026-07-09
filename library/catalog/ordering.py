from __future__ import annotations

from django.db.models import F, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from rest_framework.exceptions import ValidationError

from library.models import BookAuthor


BOOK_ORDERING_AXES = {"title", "author", "series", "series_index", "publisher"}
BOOK_ORDERINGS = BOOK_ORDERING_AXES | {f"-{axis}" for axis in BOOK_ORDERING_AXES}


def parse_ordering_param(request, *, allowed: set[str], default: str) -> str:
    raw = (request.query_params.get("ordering") or "").strip()
    if not raw:
        return default
    if raw not in allowed:
        raise ValidationError(
            {"ordering": f"Invalid ordering. Use one of: {', '.join(sorted(allowed))}."}
        )
    return raw


def parse_book_ordering(request) -> str:
    default = "series_index" if request.query_params.get("series") else "title"
    return parse_ordering_param(request, allowed=BOOK_ORDERINGS, default=default)


def apply_book_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    descending = ordering.startswith("-")
    axis = ordering.removeprefix("-")

    if axis == "title":
        return _with_title_sort(queryset).order_by(_ordered("_title_sort", descending), "title", "id")
    if axis == "author":
        return _with_primary_author_sort(queryset).order_by(
            _ordered("_primary_author_sort", descending),
            _ordered("_title_sort", descending),
            "title",
            "id",
        )
    if axis == "series":
        return _with_series_sort(queryset).order_by(
            _ordered("_series_sort", descending),
            F("book_series__series_index").asc(nulls_last=True),
            _ordered("_title_sort", descending),
            "title",
            "id",
        )
    if axis == "series_index":
        return _with_title_sort(queryset).order_by(
            _ordered("book_series__series_index", descending),
            _ordered("_title_sort", descending),
            "title",
            "id",
        )
    if axis == "publisher":
        return _with_publisher_sort(queryset).order_by(
            _ordered("_publisher_sort", descending),
            _ordered("_title_sort", descending),
            "title",
            "id",
        )
    raise ValidationError({"ordering": "Invalid ordering."})


def _ordered(field_name: str, descending: bool):
    expression = F(field_name)
    if descending:
        return expression.desc(nulls_last=True)
    return expression.asc(nulls_last=True)


def _with_title_sort(queryset: QuerySet) -> QuerySet:
    return queryset.annotate(_title_sort=Coalesce(NullIf("sort_title", Value("")), F("title")))


def _with_primary_author_sort(queryset: QuerySet) -> QuerySet:
    primary_author = (
        BookAuthor.objects.filter(book=OuterRef("pk"))
        .order_by("position", "id")
        .values("author__sort_name")[:1]
    )
    primary_author_name = (
        BookAuthor.objects.filter(book=OuterRef("pk"))
        .order_by("position", "id")
        .values("author__name")[:1]
    )
    return _with_title_sort(queryset).annotate(
        _primary_author_sort=Coalesce(
            NullIf(Subquery(primary_author), Value("")),
            Subquery(primary_author_name),
        ),
        _primary_author_name=Subquery(primary_author_name),
    )


def _with_series_sort(queryset: QuerySet) -> QuerySet:
    return _with_title_sort(queryset).annotate(
        _series_sort=Coalesce(
            NullIf("book_series__series__sort_name", Value("")),
            F("book_series__series__name"),
        )
    )


def _with_publisher_sort(queryset: QuerySet) -> QuerySet:
    return _with_title_sort(queryset).annotate(_publisher_sort=NullIf("publisher", Value("")))
