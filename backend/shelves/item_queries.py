from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, QuerySet

from library.models import BookAuthor, BookCatalogTag

from .models import Shelf, ShelfItem
from .policies import visible_books_for_shelf
from .querysets import visible_shelf_filter


def shelf_items_with_books(*, shelf: Shelf) -> QuerySet[ShelfItem]:
    return (
        ShelfItem.objects.select_related(
            "book",
            "book__book_series__series",
            "added_by",
        )
        .prefetch_related(
            Prefetch(
                "book__book_authors",
                queryset=BookAuthor.objects.select_related("author").order_by(
                    "position", "id"
                ),
            ),
            Prefetch(
                "book__book_catalog_tags",
                queryset=BookCatalogTag.objects.select_related("catalog_tag").order_by(
                    "catalog_tag__sort_name",
                    "catalog_tag__name",
                    "id",
                ),
            ),
        )
        .filter(shelf=shelf)
    )


def visible_shelf_items_for_user(user, shelf: Shelf) -> QuerySet[ShelfItem]:
    if not Shelf.objects.filter(visible_shelf_filter(user), pk=shelf.pk).exists():
        raise PermissionDenied("Not allowed.")

    visible_books = visible_books_for_shelf(user=user, shelf=shelf)
    return (
        shelf_items_with_books(shelf=shelf)
        .filter(book__in=visible_books)
        .distinct()
        .order_by("position", "created_at")
    )


def editor_shelf_items(*, shelf: Shelf) -> QuerySet[ShelfItem]:
    return shelf_items_with_books(shelf=shelf).order_by("position", "id")


def visible_shelf_item_ids(*, user, shelf: Shelf) -> set[object]:
    visible_books = visible_books_for_shelf(user=user, shelf=shelf)
    return set(
        ShelfItem.objects.filter(shelf=shelf, book__in=visible_books).values_list(
            "id", flat=True
        )
    )
