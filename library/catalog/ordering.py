from __future__ import annotations

from django.db.models import F, Min, QuerySet
from rest_framework.exceptions import ValidationError


def parse_ordering_param(request, *, allowed: set[str], default: str) -> str:
    raw = (request.query_params.get("ordering") or "").strip()
    if not raw:
        return default
    if raw not in allowed:
        raise ValidationError(
            {"ordering": f"Invalid ordering. Use one of: {', '.join(sorted(allowed))}."}
        )
    return raw


def apply_book_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    if ordering == "title":
        return queryset.order_by("title", "id")

    if ordering == "author":
        return (
            queryset.annotate(_primary_author_name=Min("authors__name"))
            .order_by(F("_primary_author_name").asc(nulls_last=True), "title", "id")
        )

    if ordering == "series":
        return queryset.order_by(
            F("series__name").asc(nulls_last=True),
            F("series_index").asc(nulls_last=True),
            "title",
            "id",
        )

    if ordering == "series_index":
        return queryset.order_by(
            F("series_index").asc(nulls_last=True),
            "title",
            "id",
        )

    raise ValidationError({"ordering": "Invalid ordering."})


def apply_taxonomy_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    if ordering == "name":
        return queryset.order_by("name", "id")
    if ordering == "-book_count":
        return queryset.order_by("-book_count", "name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


def apply_group_ordering(queryset: QuerySet, ordering: str) -> QuerySet:
    if ordering == "name":
        return queryset.order_by("name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


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
            queryset.annotate(_primary_author_name=Min("book__authors__name"))
            .order_by(F("_primary_author_name").asc(nulls_last=True), "book__title", "id")
        )
    raise ValidationError({"ordering": "Invalid ordering."})
