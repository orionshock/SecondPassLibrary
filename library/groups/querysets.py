from __future__ import annotations

from uuid import UUID

from django.db.models import F, QuerySet
from rest_framework.exceptions import ValidationError

from library.models import LibraryGroup


GROUP_ORDERINGS = {"name", "-name"}


def filter_groups_by_book(
    queryset: QuerySet[LibraryGroup], query_params
) -> QuerySet[LibraryGroup]:
    if "book" not in query_params:
        return queryset

    raw_book_id = str(query_params.get("book") or "").strip()
    try:
        book_id = UUID(raw_book_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError({"book": "Must be a valid UUID."}) from exc

    return queryset.filter(book_assignments__book_id=book_id).distinct()


def apply_group_search(queryset: QuerySet[LibraryGroup], query_params) -> QuerySet[LibraryGroup]:
    raw_query = str(query_params.get("q") or "").strip()
    if not raw_query:
        return queryset
    return queryset.filter(name__icontains=raw_query) | queryset.filter(
        description__icontains=raw_query
    )


def parse_group_ordering(request) -> str:
    raw = str(request.query_params.get("ordering") or "").strip()
    if not raw:
        return "name"
    if raw not in GROUP_ORDERINGS:
        raise ValidationError(
            {"ordering": f"Invalid ordering. Use one of: {', '.join(sorted(GROUP_ORDERINGS))}."}
        )
    return raw


def apply_group_ordering(queryset: QuerySet[LibraryGroup], ordering: str) -> QuerySet[LibraryGroup]:
    if ordering == "name":
        return queryset.order_by("name", "id")
    if ordering == "-name":
        return queryset.order_by(F("name").desc(nulls_last=True), "id")
    raise ValidationError({"ordering": "Invalid ordering."})
