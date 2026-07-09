from __future__ import annotations

from django.db.models import F, Min, QuerySet
from rest_framework.exceptions import ValidationError


# LibraryReWrite2607 temporary importability scaffolding for shelves. Replace
# this module when shelves are reconnected to the new library query services.
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
