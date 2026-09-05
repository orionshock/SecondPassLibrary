from __future__ import annotations

from django.db.models import QuerySet

from library.catalog.axes import apply_axis_ordering, visible_tags_from_books
from library.models import Book, CatalogTag


def catalog_tag_aggregates(books: QuerySet[Book]) -> QuerySet[CatalogTag]:
    """Return name-ordered Catalog Tag counts for a distinct Book population."""
    return apply_axis_ordering(visible_tags_from_books(books), "name")
