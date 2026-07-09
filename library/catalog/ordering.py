from __future__ import annotations

from django.db.models import F, Min, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from rest_framework.exceptions import ValidationError

from library.models import BookAuthor


BOOK_ORDERINGS = {"title", "author", "series", "series_index"}


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
    if ordering == "title":
        return _with_title_sort(queryset).order_by("_title_sort", "title", "id")
    if ordering == "author":
        return _with_primary_author_sort(queryset).order_by(
            F("_primary_author_sort").asc(nulls_last=True),
            "_title_sort",
            "title",
            "id",
        )
    if ordering == "series":
        return _with_series_sort(queryset).order_by(
            F("_series_sort").asc(nulls_last=True),
            F("book_series__series_index").asc(nulls_last=True),
            "_title_sort",
            "title",
            "id",
        )
    if ordering == "series_index":
        return _with_title_sort(queryset).order_by(
            F("book_series__series_index").asc(nulls_last=True),
            "_title_sort",
            "title",
            "id",
        )
    raise ValidationError({"ordering": "Invalid ordering."})


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


def apply_shelf_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    if ordering == "name":
        return queryset.order_by("name", "id")
    if ordering == "-item_count":
        return queryset.order_by("-item_count", "name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


def apply_shelf_item_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    if ordering == "position":
        return queryset.order_by("position", "id", "book_id")
    if ordering == "title":
        return queryset.order_by("book__title", "id", "book_id")
    if ordering == "author":
        return (
            queryset.annotate(_primary_author_name=Min("book__authors__sort_name"))
            .order_by(F("_primary_author_name").asc(nulls_last=True), "book__title", "id")
        )
    raise ValidationError({"ordering": "Invalid ordering."})
