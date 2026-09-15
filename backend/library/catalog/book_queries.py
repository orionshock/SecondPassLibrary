from __future__ import annotations

from django.db.models import Prefetch

from library.catalog.filters import (
    apply_book_filters,
    apply_broad_book_search,
    apply_catalog_tag_filter,
)
from library.catalog.ordering import apply_book_ordering
from library.models import BookAuthor, BookCatalogTag
from library.queries import visible_groups_for_user


def book_row_queryset(queryset, *, book_path: str = ""):
    """Load the ordered relationships required by a serialized Book row."""
    prefix = f"{book_path}__" if book_path else ""
    return queryset.select_related(
        f"{prefix}book_series__series"
    ).prefetch_related(
        Prefetch(
            f"{prefix}book_authors",
            queryset=BookAuthor.objects.select_related("author").order_by(
                "position", "id"
            ),
        ),
        Prefetch(
            f"{prefix}book_catalog_tags",
            queryset=BookCatalogTag.objects.select_related("catalog_tag").order_by(
                "catalog_tag__sort_name",
                "catalog_tag__name",
                "id",
            ),
        ),
    )


def book_detail_queryset(queryset):
    return book_row_queryset(queryset).prefetch_related("identifiers")


def book_browse_queryset(queryset, *, query_params, ordering: str):
    queryset = apply_book_filters(queryset, query_params)
    queryset = apply_book_ordering(queryset, ordering)
    return book_row_queryset(queryset)


def book_search_queryset(queryset, *, term: str, query_params, ordering: str):
    if not term:
        queryset = queryset.none()
    else:
        queryset = apply_broad_book_search(queryset, term)
        queryset = apply_catalog_tag_filter(queryset, query_params)
    queryset = apply_book_ordering(queryset, ordering)
    return book_row_queryset(queryset)


def attach_visible_groups_to_book(*, book, user):
    book._visible_groups = list(
        visible_groups_for_user(user)
        .filter(book_assignments__book=book)
        .order_by("name", "id")
    )
    return book
