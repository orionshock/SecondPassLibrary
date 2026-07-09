from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db.models import Count, F, Min, OuterRef, Q, QuerySet, Subquery
from rest_framework.exceptions import ValidationError

from library.queries import visible_books_for_user

from .models import Shelf, ShelfItem
from .policies import visible_shelf_filter


@dataclass(frozen=True)
class ShelfListFilters:
    scope: str | None = None
    owner_group_id: UUID | None = None
    book_id: UUID | None = None


def _parse_uuid_query_param(query_params, name: str) -> UUID | None:
    if name not in query_params:
        return None

    raw_value = str(query_params.get(name) or "").strip()
    try:
        return UUID(raw_value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError({name: "Must be a valid UUID."}) from exc


def parse_shelf_list_filters(query_params) -> ShelfListFilters:
    scope: str | None = None
    if "scope" in query_params:
        scope = str(query_params.get("scope") or "").strip().lower()
        if scope not in {"personal", "shared"}:
            raise ValidationError(
                {"scope": "Must be one of: personal, shared."}
            )

    owner_group_id = _parse_uuid_query_param(query_params, "owner_group")
    book_id = _parse_uuid_query_param(query_params, "book")

    if scope == "personal" and owner_group_id is not None:
        raise ValidationError(
            {
                "owner_group": (
                    "Cannot be combined with scope=personal because personal "
                    "shelves are user-owned."
                )
            }
        )

    return ShelfListFilters(
        scope=scope,
        owner_group_id=owner_group_id,
        book_id=book_id,
    )


def build_visible_shelf_list_queryset(
    *,
    queryset: QuerySet[Shelf],
    user: Any,
    query_params,
) -> QuerySet[Shelf]:
    filters = parse_shelf_list_filters(query_params)
    visible_qs = queryset.filter(visible_shelf_filter(user)).distinct()

    if filters.scope == "personal":
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=user,
        )
    elif filters.scope == "shared":
        visible_qs = visible_qs.exclude(
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=user,
        )

    if filters.owner_group_id is not None:
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group_id=filters.owner_group_id,
        )

    if filters.book_id is not None:
        visible_qs = visible_qs.filter(
            items__book_id=filters.book_id,
        ).distinct()
        visible_qs = visible_qs.annotate(
            matched_item_id=Subquery(
                ShelfItem.objects.filter(
                    shelf_id=OuterRef("pk"),
                    book_id=filters.book_id,
                ).values("id")[:1]
            )
        )

    return visible_qs


def with_visible_item_count(queryset: QuerySet[Shelf], *, user: Any) -> QuerySet[Shelf]:
    visible_books = visible_books_for_user(user, cached=False)
    visible_item_filter = (
        Q(owner_type=Shelf.OWNER_TYPE_USER, items__book__in=visible_books)
        | Q(
            owner_type=Shelf.OWNER_TYPE_GROUP,
            items__book__group_assignments__group=F("owner_group"),
        )
    )
    return queryset.annotate(
        item_count=Count("items", filter=visible_item_filter, distinct=True)
    )


def apply_shelf_ordering(queryset: QuerySet[Shelf], ordering: str) -> QuerySet[Shelf]:
    if ordering == "name":
        return queryset.order_by("name", "id")
    if ordering == "-item_count":
        return queryset.order_by("-item_count", "name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


def apply_shelf_item_ordering(queryset: QuerySet[ShelfItem], ordering: str) -> QuerySet[ShelfItem]:
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
