from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils import timezone

from core import policies as core_policies
from library.models import Book

from . import policies
from .models import Shelf, ShelfItem


def _normalized_title(value: str | None) -> str:
    return (value or "").casefold()


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

    if not policies.can_create_shelf(
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
    if not policies.can_edit_shelf(user=actor, shelf=shelf):
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
    if not policies.can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    shelf.delete()


def add_book_to_shelf(actor, shelf: Shelf, book: Book, position: int | None = None) -> ShelfItem:
    if not policies.can_add_book_to_shelf(user=actor, book=book, shelf=shelf):
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
            raise ValidationError("This book is already on the shelf.")
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

    if not policies.can_remove_book_from_shelf(user=actor, book=book, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    if item is None:
        return False

    with transaction.atomic():
        item.delete()
        canonicalize_shelf_positions(shelf)
    return True


def set_shelf_item_position(actor, shelf: Shelf, item: ShelfItem, position: int) -> ShelfItem:
    if not policies.can_edit_shelf(user=actor, shelf=shelf):
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
    if not policies.can_edit_shelf(user=actor, shelf=shelf):
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
    if not policies.can_view_shelf(user=user, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    qs = ShelfItem.objects.select_related("book").filter(shelf=shelf)

    # Safety rule: shelves never grant access.
    if core_policies.can_manage_library(user):
        return qs.order_by("position", "created_at")

    # Mirror core.policies.can_view_book: viewable if the viewer is a member of
    # at least one group the book is assigned to.
    return (
        qs.filter(book__group_assignments__group__memberships__user=user)
        .distinct()
        .order_by("position", "created_at")
    )
