from __future__ import annotations

from .models import Shelf, ShelfItem
from .services import canonicalize_shelf_positions


def remove_book_from_group_owned_shelves(*, book, group) -> None:
    shelf_ids = list(
        ShelfItem.objects.filter(
            book=book,
            shelf__owner_type=Shelf.OWNER_TYPE_GROUP,
            shelf__owner_group=group,
        )
        .order_by()
        .values_list("shelf_id", flat=True)
        .distinct()
    )
    if not shelf_ids:
        return

    ShelfItem.objects.filter(shelf_id__in=shelf_ids, book=book).delete()
    for shelf in Shelf.objects.filter(id__in=shelf_ids):
        canonicalize_shelf_positions(shelf)
