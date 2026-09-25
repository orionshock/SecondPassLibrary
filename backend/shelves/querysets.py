from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet, Subquery
from rest_framework.exceptions import ValidationError

from accounts.roles import is_librarian
from library.queries import effective_group_ids_for_user, visible_books_for_user
from library.catalog.ordering import with_primary_author_sort

from .models import Shelf, ShelfItem


@dataclass(frozen=True)
class ShelfListFilters:
    scope: str | None = None
    owner_group_id: UUID | None = None
    book_id: UUID | None = None
    query: str = ""


def visible_shelf_filter(user) -> Q:
    if getattr(user, "is_anonymous", False):
        return Q(pk__isnull=True)

    user_shelves = Q(owner_type=Shelf.OWNER_TYPE_USER, owner_user=user) | Q(
        owner_type=Shelf.OWNER_TYPE_USER,
        visibility=Shelf.VISIBILITY_LISTED,
    )
    group_shelves = Q(
        owner_type=Shelf.OWNER_TYPE_GROUP,
        owner_group_id__in=effective_group_ids_for_user(user),
    )
    if is_librarian(user):
        group_shelves = Q(owner_type=Shelf.OWNER_TYPE_GROUP)

    return user_shelves | group_shelves


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
        if scope not in {"all", "personal", "shared", "group"}:
            raise ValidationError(
                {"scope": "Must be one of: all, personal, shared, group."}
            )

    owner_group_id = _parse_uuid_query_param(query_params, "owner_group")
    book_id = _parse_uuid_query_param(query_params, "book")
    query = str(query_params.get("q") or "").strip()

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
        query=query,
    )


def filter_readable_shelves(
    queryset: QuerySet[Shelf], *, user: Any
) -> QuerySet[Shelf]:
    """Apply the common list/detail Shelf read policy.

    The queryset must already have the viewer-scoped ``item_count`` annotation.
    """
    return (
        queryset.filter(visible_shelf_filter(user))
        .filter(
            Q(owner_type=Shelf.OWNER_TYPE_GROUP)
            | Q(owner_type=Shelf.OWNER_TYPE_USER, owner_user=user)
            | Q(item_count__gt=0)
        )
        .distinct()
    )


def build_visible_shelf_list_queryset(
    *,
    queryset: QuerySet[Shelf],
    user: Any,
    query_params,
) -> QuerySet[Shelf]:
    filters = parse_shelf_list_filters(query_params)
    visible_books = visible_books_for_user(user, cached=False)
    has_visible_item = ShelfItem.objects.filter(
        shelf_id=OuterRef("pk"),
        book__in=visible_books,
    )
    visible_qs = (
        queryset.filter(visible_shelf_filter(user))
        .alias(_has_visible_item=Exists(has_visible_item))
        .filter(
            Q(owner_type=Shelf.OWNER_TYPE_GROUP)
            | Q(owner_type=Shelf.OWNER_TYPE_USER, owner_user=user)
            | Q(_has_visible_item=True)
        )
    )

    if filters.scope == "personal":
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=user,
        )
    elif filters.scope == "shared":
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_LISTED,
        ).exclude(owner_user=user)
    elif filters.scope == "group":
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_GROUP,
        )

    if filters.owner_group_id is not None:
        visible_qs = visible_qs.filter(
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group_id=filters.owner_group_id,
        )

    if filters.query:
        name_match = Q(name__icontains=filters.query)
        if filters.scope == "personal":
            search_filter = name_match
        elif filters.scope == "shared":
            search_filter = name_match | Q(
                owner_type=Shelf.OWNER_TYPE_USER,
                owner_user__username__icontains=filters.query,
            )
        elif filters.scope == "group":
            search_filter = name_match | Q(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group__name__icontains=filters.query,
            )
        else:
            search_filter = (
                name_match
                | Q(
                    owner_type=Shelf.OWNER_TYPE_USER,
                    owner_user__username__icontains=filters.query,
                )
                | Q(
                    owner_type=Shelf.OWNER_TYPE_GROUP,
                    owner_group__name__icontains=filters.query,
                )
            )
        visible_qs = visible_qs.filter(search_filter)

    if filters.book_id is not None:
        visible_item_filter = (
            Q(owner_type=Shelf.OWNER_TYPE_USER, items__book__in=visible_books)
            | Q(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                items__book__group_assignments__group=F("owner_group"),
            )
        )
        visible_qs = visible_qs.filter(
            visible_item_filter,
            items__book_id=filters.book_id,
        ).distinct()
        visible_qs = visible_qs.annotate(
            matched_item_id=Subquery(
                ShelfItem.objects.filter(
                    shelf_id=OuterRef("pk"),
                    book_id=filters.book_id,
                )
                .filter(
                    Q(shelf__owner_type=Shelf.OWNER_TYPE_USER, book__in=visible_books)
                    | Q(
                        shelf__owner_type=Shelf.OWNER_TYPE_GROUP,
                        book__group_assignments__group_id=OuterRef("owner_group_id"),
                    )
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
    if ordering == "-name":
        return queryset.order_by("-name", "id")
    if ordering == "item_count":
        return queryset.order_by("item_count", "name", "id")
    if ordering == "-item_count":
        return queryset.order_by("-item_count", "name", "id")
    raise ValidationError({"ordering": "Invalid ordering."})


def apply_shelf_item_ordering(queryset: QuerySet[ShelfItem], ordering: str) -> QuerySet[ShelfItem]:
    if ordering == "position":
        return queryset.order_by("position", "id", "book_id")
    if ordering == "-position":
        return queryset.order_by("-position", "id", "book_id")
    if ordering == "title":
        return queryset.order_by("book__title", "id", "book_id")
    if ordering == "-title":
        return queryset.order_by("-book__title", "id", "book_id")
    if ordering in {"author", "-author"}:
        descending = ordering.startswith("-")
        author_order = (
            F("_primary_author_sort").desc(nulls_last=True)
            if descending
            else F("_primary_author_sort").asc(nulls_last=True)
        )
        title_order = "-book__title" if descending else "book__title"
        return (
            with_primary_author_sort(queryset, book_id_field="book_id")
            .order_by(author_order, title_order, "id")
        )
    raise ValidationError({"ordering": "Invalid ordering."})
