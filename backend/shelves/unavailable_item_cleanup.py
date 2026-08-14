from __future__ import annotations

from dataclasses import dataclass
import logging
from uuid import UUID

from django.db import transaction

from library.queries import visible_books_for_user

from .models import Shelf, ShelfItem
from .item_services import canonicalize_shelf_positions


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShelfCleanupEntry:
    shelf_id: UUID
    shelf_name: str
    unavailable_item_ids: tuple[UUID, ...]

    @property
    def unavailable_item_count(self) -> int:
        return len(self.unavailable_item_ids)


@dataclass(frozen=True)
class ShelfCleanupPlan:
    shelves: tuple[ShelfCleanupEntry, ...]

    @property
    def affected_shelf_count(self) -> int:
        return len(self.shelves)

    @property
    def unavailable_item_count(self) -> int:
        return sum(entry.unavailable_item_count for entry in self.shelves)


@dataclass(frozen=True)
class ShelfCleanupResult:
    affected_shelf_count: int
    removed_item_count: int


def plan_unavailable_user_shelf_items(*, lock: bool = False) -> ShelfCleanupPlan:
    shelves = Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_USER).select_related(
        "owner_user"
    )
    if lock:
        shelves = shelves.select_for_update()

    visible_ids_by_owner: dict[object, set[UUID]] = {}
    entries: list[ShelfCleanupEntry] = []
    for shelf in shelves.order_by("id"):
        owner = shelf.owner_user
        if owner is None:
            continue
        if owner.pk not in visible_ids_by_owner:
            visible_ids_by_owner[owner.pk] = set(
                visible_books_for_user(owner, cached=False).values_list("id", flat=True)
            )
        items = ShelfItem.objects.filter(shelf=shelf).order_by("id")
        if lock:
            items = items.select_for_update()
        unavailable_ids = tuple(
            item_id
            for item_id, book_id in items.values_list("id", "book_id")
            if book_id not in visible_ids_by_owner[owner.pk]
        )
        if unavailable_ids:
            entries.append(
                ShelfCleanupEntry(
                    shelf_id=shelf.id,
                    shelf_name=shelf.name,
                    unavailable_item_ids=unavailable_ids,
                )
            )
    return ShelfCleanupPlan(shelves=tuple(entries))


def cleanup_unavailable_user_shelf_items() -> ShelfCleanupResult:
    with transaction.atomic():
        plan = plan_unavailable_user_shelf_items(lock=True)
        removed = 0
        for entry in plan.shelves:
            deleted, _details = ShelfItem.objects.filter(
                shelf_id=entry.shelf_id,
                id__in=entry.unavailable_item_ids,
            ).delete()
            removed += deleted
            shelf = Shelf.objects.get(pk=entry.shelf_id)
            canonicalize_shelf_positions(shelf)

    result = ShelfCleanupResult(
        affected_shelf_count=plan.affected_shelf_count,
        removed_item_count=removed,
    )
    logger.info(
        "Shelf cleanup completed: affected_shelves=%s removed_items=%s",
        result.affected_shelf_count,
        result.removed_item_count,
    )
    return result
