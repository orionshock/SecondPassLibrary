from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Prefetch, QuerySet
from django.utils import timezone

from accounts.roles import is_librarian
from library.groups.public_group import is_public_group
from library.models import Book, BookAuthor, BookCatalogTag
from library.queries import visible_books_for_group, visible_books_for_user
from library.roles import is_curator

from .models import Shelf, ShelfItem
from .querysets import visible_shelf_filter


def _normalized_title(value: str | None) -> str:
    return (value or "").casefold()


def can_create_shelf(
    *,
    user,
    owner_type: str,
    owner_user=None,
    owner_group=None,
) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if owner_type == Shelf.OWNER_TYPE_USER:
        target_user = owner_user or user
        return getattr(target_user, "id", None) == getattr(user, "id", None)

    if owner_type == Shelf.OWNER_TYPE_GROUP:
        if owner_group is None:
            return False
        if is_librarian(user):
            return True
        if is_public_group(owner_group):
            return False
        return is_curator(user, owner_group)

    return False


def can_edit_shelf(*, user, shelf: Shelf) -> bool:
    if getattr(user, "is_anonymous", False):
        return False

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        owner_user_id = getattr(shelf, "owner_user_id", None)
        return owner_user_id == getattr(user, "id", None)

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        group = shelf.owner_group
        if group is None:
            return False
        return can_create_shelf(
            user=user,
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )

    return False


def books_available_to_shelf_editor(*, user, shelf: Shelf) -> QuerySet[Book]:
    if not can_edit_shelf(user=user, shelf=shelf):
        return Book.objects.none()

    if shelf.owner_type == Shelf.OWNER_TYPE_USER:
        return visible_books_for_user(user, cached=False)

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
        group = shelf.owner_group
        if group is None:
            return Book.objects.none()
        return visible_books_for_group(user, group, cached=False)

    return Book.objects.none()


def _can_add_book_to_shelf(*, user, book: Book, shelf: Shelf) -> bool:
    return books_available_to_shelf_editor(user=user, shelf=shelf).filter(pk=book.pk).exists()


def canonicalize_shelf_positions(shelf: Shelf) -> list[ShelfItem]:
    items = list(ShelfItem.objects.select_related("book").filter(shelf=shelf))
    items.sort(
        key=lambda item: (
            item.position,
            _normalized_title(item.book.title),
            str(item.book_id),
            str(item.id),
        )
    )

    changed: list[ShelfItem] = []
    now = timezone.now()
    for position, item in enumerate(items):
        if item.position != position:
            item.position = position
            item.updated_at = now
            changed.append(item)

    if changed:
        ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])

    return items


def create_shelf(
    actor,
    *,
    name: str,
    description: str = "",
    owner_type: str,
    owner_user=None,
    owner_group=None,
    visibility: str = Shelf.VISIBILITY_PRIVATE,
) -> Shelf:
    if owner_type == Shelf.OWNER_TYPE_USER:
        owner_user = owner_user or actor

    if not can_create_shelf(
        user=actor,
        owner_type=owner_type,
        owner_user=owner_user,
        owner_group=owner_group,
    ):
        raise PermissionDenied("Not allowed.")

    shelf = Shelf(
        name=name,
        description=description,
        owner_type=owner_type,
        owner_user=owner_user,
        owner_group=owner_group,
        visibility=visibility,
        created_by=actor,
    )

    shelf.save()
    return shelf


def update_shelf(actor, shelf: Shelf, **fields: Any) -> Shelf:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    # Owner fields are immutable after creation.
    forbidden = {"owner_type", "owner_user", "owner_user_id", "owner_group", "owner_group_id", "created_by", "created_by_id"}
    if forbidden.intersection(fields.keys()):
        raise ValidationError("Shelf owner fields cannot be changed.")

    allowed = {"name", "description", "visibility"}
    for k in list(fields.keys()):
        if k not in allowed:
            raise ValidationError(f"Unsupported field: {k}")

    for k, v in fields.items():
        setattr(shelf, k, v)
    shelf.save()
    return shelf


def delete_shelf(actor, shelf: Shelf) -> None:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    shelf.delete()


def add_book_to_shelf(actor, shelf: Shelf, book: Book, position: int | None = None) -> ShelfItem:
    if not _can_add_book_to_shelf(user=actor, book=book, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    with transaction.atomic():
        if position is None:
            canonicalize_shelf_positions(shelf)
            max_position = (
                ShelfItem.objects.filter(shelf=shelf).aggregate(m=Max("position")).get("m")
            )
            position = (int(max_position) + 1) if max_position is not None else 0

        item, created = ShelfItem.objects.get_or_create(
            shelf=shelf,
            book=book,
            defaults={"position": position, "added_by": actor},
        )
        if not created:
            raise ValidationError({"book": "This book is already on the shelf."})
        canonicalize_shelf_positions(shelf)
        item.refresh_from_db()
        return item


def remove_book_from_shelf(actor, shelf: Shelf, book_or_item) -> bool:
    if isinstance(book_or_item, ShelfItem):
        item = book_or_item
        book = item.book
    else:
        book = book_or_item
        item = ShelfItem.objects.filter(shelf=shelf, book=book).first()

    if not isinstance(book, Book):
        raise ValidationError("Invalid book/item.")

    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    if item is None:
        return False

    with transaction.atomic():
        item.delete()
        canonicalize_shelf_positions(shelf)
    return True


def set_shelf_item_position(actor, shelf: Shelf, item: ShelfItem, position: int) -> ShelfItem:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    if item.shelf_id != shelf.id:
        raise ValidationError("Shelf item does not belong to this shelf.")

    with transaction.atomic():
        ordered = canonicalize_shelf_positions(shelf)
        ids = [ordered_item.id for ordered_item in ordered]
        try:
            current_index = ids.index(item.id)
        except ValueError as exc:
            raise ValidationError("Shelf item does not belong to this shelf.") from exc

        target_index = max(0, min(int(position), len(ordered) - 1))
        if target_index != current_index:
            moving = ordered.pop(current_index)
            ordered.insert(target_index, moving)

            now = timezone.now()
            changed: list[ShelfItem] = []
            for new_position, ordered_item in enumerate(ordered):
                if ordered_item.position != new_position:
                    ordered_item.position = new_position
                    ordered_item.updated_at = now
                    changed.append(ordered_item)
            if changed:
                ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])

        item.refresh_from_db()
        return item


def move_shelf_item(actor, shelf: Shelf, item: ShelfItem, direction: str) -> ShelfItem:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    if item.shelf_id != shelf.id:
        raise ValidationError("Shelf item does not belong to this shelf.")
    if direction not in {"up", "down"}:
        raise ValidationError("Invalid move direction.")

    with transaction.atomic():
        ordered = canonicalize_shelf_positions(shelf)
        ids = [ordered_item.id for ordered_item in ordered]
        try:
            index = ids.index(item.id)
        except ValueError as exc:
            raise ValidationError("Shelf item does not belong to this shelf.") from exc

        target_index = index - 1 if direction == "up" else index + 1
        if target_index < 0 or target_index >= len(ordered):
            item.refresh_from_db()
            return item

        moving = ordered.pop(index)
        ordered.insert(target_index, moving)

        now = timezone.now()
        changed: list[ShelfItem] = []
        for new_position, ordered_item in enumerate(ordered):
            if ordered_item.position != new_position:
                ordered_item.position = new_position
                ordered_item.updated_at = now
                changed.append(ordered_item)
        if changed:
            ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])

        item.refresh_from_db()
        return item


def visible_shelf_items_for_user(user, shelf: Shelf) -> QuerySet[ShelfItem]:
    if not Shelf.objects.filter(visible_shelf_filter(user), pk=shelf.pk).exists():
        raise PermissionDenied("Not allowed.")

    qs = (
        ShelfItem.objects.select_related("book", "book__book_series__series")
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

    if shelf.owner_type == Shelf.OWNER_TYPE_GROUP and shelf.owner_group is not None:
        visible_books = visible_books_for_group(user, shelf.owner_group, cached=False)
    else:
        visible_books = visible_books_for_user(user, cached=False)

    return qs.filter(book__in=visible_books).distinct().order_by("position", "created_at")
