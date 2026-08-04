from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from library.models import Book

from .models import Shelf, ShelfItem
from .policies import books_available_to_shelf_editor, can_edit_shelf, visible_books_for_shelf


DIRECT_POSITION_UNAVAILABLE = (
    "Direct positioning is unavailable while this shelf contains unavailable items."
)


def _normalized_title(value: str | None) -> str:
    return (value or "").casefold()


def _lock_shelf_and_items(shelf: Shelf) -> tuple[Shelf, list[ShelfItem]]:
    locked_shelf = (
        Shelf.objects.select_for_update()
        .select_related("owner_group", "owner_user")
        .get(pk=shelf.pk)
    )
    items = list(
        ShelfItem.objects.select_for_update()
        .select_related("book")
        .filter(shelf=locked_shelf)
    )
    return locked_shelf, items


def _canonicalize_locked_items(items: list[ShelfItem]) -> list[ShelfItem]:
    items.sort(
        key=lambda item: (
            item.position,
            _normalized_title(item.book.title),
            str(item.book_id),
            str(item.id),
        )
    )
    now = timezone.now()
    changed: list[ShelfItem] = []
    for position, item in enumerate(items):
        if item.position != position:
            item.position = position
            item.updated_at = now
            changed.append(item)
    if changed:
        ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])
    return items


def _visible_item_ids(*, actor, shelf: Shelf, items: list[ShelfItem]) -> set[object]:
    item_ids = [item.id for item in items]
    return set(
        ShelfItem.objects.filter(
            id__in=item_ids,
            book__in=visible_books_for_shelf(user=actor, shelf=shelf),
        ).values_list("id", flat=True)
    )


def canonicalize_shelf_positions(shelf: Shelf) -> list[ShelfItem]:
    with transaction.atomic():
        _locked_shelf, items = _lock_shelf_and_items(shelf)
        return _canonicalize_locked_items(items)


def add_book_to_shelf(
    actor,
    shelf: Shelf,
    book: Book,
    position: int | None = None,
) -> ShelfItem:
    if not books_available_to_shelf_editor(user=actor, shelf=shelf).filter(
        pk=book.pk
    ).exists():
        raise PermissionDenied("Not allowed.")

    with transaction.atomic():
        locked_shelf, items = _lock_shelf_and_items(shelf)
        if not can_edit_shelf(user=actor, shelf=locked_shelf):
            raise PermissionDenied("Not allowed.")
        if not visible_books_for_shelf(user=actor, shelf=locked_shelf).filter(
            pk=book.pk
        ).exists():
            raise PermissionDenied("Not allowed.")
        ordered = _canonicalize_locked_items(items)
        visible_ids = _visible_item_ids(actor=actor, shelf=locked_shelf, items=ordered)
        if position is not None and len(visible_ids) != len(ordered):
            raise ValidationError({"position": DIRECT_POSITION_UNAVAILABLE})
        if position is None:
            position = len(ordered)

        if any(item.book_id == book.id for item in ordered):
            raise ValidationError({"book": "This book is already on the shelf."})
        item = ShelfItem.objects.create(
            shelf=locked_shelf,
            book=book,
            position=position,
            added_by=actor,
        )
        ordered.append(item)
        _canonicalize_locked_items(ordered)
        item.refresh_from_db()
        return item


def remove_book_from_shelf(actor, shelf: Shelf, book_or_item) -> bool:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    item_id = book_or_item.id if isinstance(book_or_item, ShelfItem) else None
    book_id = book_or_item.id if isinstance(book_or_item, Book) else None
    if item_id is None and book_id is None:
        raise ValidationError("Invalid book/item.")

    with transaction.atomic():
        locked_shelf, items = _lock_shelf_and_items(shelf)
        if not can_edit_shelf(user=actor, shelf=locked_shelf):
            raise PermissionDenied("Not allowed.")
        item = next(
            (
                candidate
                for candidate in items
                if candidate.id == item_id
                or (item_id is None and candidate.book_id == book_id)
            ),
            None,
        )
        if item is None:
            return False
        item.delete()
        _canonicalize_locked_items(
            [candidate for candidate in items if candidate.id != item.id]
        )
        return True


def remove_group_book_from_shelf(*, shelf: Shelf, book: Book) -> bool:
    """Remove a group Book under the same per-shelf locking boundary."""
    with transaction.atomic():
        _locked_shelf, items = _lock_shelf_and_items(shelf)
        item = next(
            (candidate for candidate in items if candidate.book_id == book.id),
            None,
        )
        if item is None:
            return False
        item.delete()
        _canonicalize_locked_items(
            [candidate for candidate in items if candidate.id != item.id]
        )
        return True


def set_shelf_item_position(
    actor,
    shelf: Shelf,
    item: ShelfItem,
    position: int,
) -> ShelfItem:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    if item.shelf_id != shelf.id:
        raise ValidationError("Shelf item does not belong to this shelf.")

    with transaction.atomic():
        locked_shelf, items = _lock_shelf_and_items(shelf)
        ordered = _canonicalize_locked_items(items)
        visible_ids = _visible_item_ids(actor=actor, shelf=locked_shelf, items=ordered)
        if item.id not in visible_ids:
            raise PermissionDenied("Not allowed.")
        if len(visible_ids) != len(ordered):
            raise ValidationError({"position": DIRECT_POSITION_UNAVAILABLE})

        ids = [candidate.id for candidate in ordered]
        try:
            current_index = ids.index(item.id)
        except ValueError as exc:
            raise ValidationError("Shelf item does not belong to this shelf.") from exc
        target_index = max(0, min(int(position), len(ordered) - 1))
        if target_index != current_index:
            moving = ordered.pop(current_index)
            ordered.insert(target_index, moving)
            _write_positions(ordered)
        item.refresh_from_db()
        return item


def move_shelf_item(
    actor,
    shelf: Shelf,
    item: ShelfItem,
    direction: str,
) -> ShelfItem:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    if item.shelf_id != shelf.id:
        raise ValidationError("Shelf item does not belong to this shelf.")
    if direction not in {"up", "down"}:
        raise ValidationError("Invalid move direction.")

    with transaction.atomic():
        locked_shelf, items = _lock_shelf_and_items(shelf)
        ordered = _canonicalize_locked_items(items)
        visible_ids = _visible_item_ids(actor=actor, shelf=locked_shelf, items=ordered)
        if item.id not in visible_ids:
            raise PermissionDenied("Not allowed.")

        index = next(
            (i for i, candidate in enumerate(ordered) if candidate.id == item.id),
            None,
        )
        if index is None:
            raise ValidationError("Shelf item does not belong to this shelf.")
        step = -1 if direction == "up" else 1
        target_index = index + step
        while 0 <= target_index < len(ordered):
            if ordered[target_index].id in visible_ids:
                break
            target_index += step
        else:
            item.refresh_from_db()
            return item

        moving = ordered[index]
        target = ordered[target_index]
        moving.position, target.position = target.position, moving.position
        now = timezone.now()
        moving.updated_at = now
        target.updated_at = now
        ShelfItem.objects.bulk_update(
            [moving, target], ["position", "updated_at"]
        )
        item.refresh_from_db()
        return item


def _write_positions(ordered: list[ShelfItem]) -> None:
    now = timezone.now()
    changed: list[ShelfItem] = []
    for position, item in enumerate(ordered):
        if item.position != position:
            item.position = position
            item.updated_at = now
            changed.append(item)
    if changed:
        ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])
