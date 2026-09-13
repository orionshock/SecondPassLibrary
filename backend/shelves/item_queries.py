from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import F, Prefetch, Q, QuerySet, Window
from django.db.models.functions import RowNumber

from library.catalog.preview_books import attach_preview_books_from_queryset
from library.models import BookAuthor, BookCatalogTag
from library.queries import visible_books_for_user

from .models import Shelf, ShelfItem
from .policies import visible_books_for_shelf
from .querysets import visible_shelf_filter


def attach_shelf_preview_books(*, shelves, user, limit: int) -> None:
    shelf_list = list(shelves)
    if not shelf_list:
        return

    visible_books = visible_books_for_user(user, cached=False)
    readable_shelves = Shelf.objects.filter(visible_shelf_filter(user))
    rows = (
        ShelfItem.objects.filter(
            shelf_id__in=[shelf.id for shelf in shelf_list],
            shelf__in=readable_shelves,
            book__in=visible_books,
        )
        .filter(
            Q(shelf__owner_type=Shelf.OWNER_TYPE_USER)
            | Q(
                shelf__owner_type=Shelf.OWNER_TYPE_GROUP,
                book__group_assignments__group_id=F("shelf__owner_group_id"),
            )
        )
        .select_related("book")
        .only(
            "id",
            "shelf_id",
            "position",
            "book__id",
            "book__title",
            "book__cover_file",
        )
        .annotate(
            _preview_parent_id=F("shelf_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("shelf_id")],
                order_by=[F("position").asc(), F("id").asc()],
            ),
        )
        .filter(_preview_rank__lte=limit)
        .order_by("shelf_id", "_preview_rank")
    )
    attach_preview_books_from_queryset(
        parents=shelf_list,
        queryset=rows,
        get_book=lambda row: row.book,
    )


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
