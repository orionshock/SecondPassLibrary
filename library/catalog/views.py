from __future__ import annotations

from django.db.models import Prefetch
from rest_framework.generics import ListAPIView, RetrieveAPIView

from library.catalog.filters import apply_book_filters
from library.catalog.ordering import apply_book_ordering, parse_book_ordering
from library.catalog.serializers import BookDetailSerializer, BookListSerializer
from library.models import BookAuthor, BookCatalogTag
from library.queries import visible_books_for_user


def book_browse_queryset(queryset):
    return queryset.select_related("book_series__series").prefetch_related(
        Prefetch(
            "book_authors",
            queryset=BookAuthor.objects.select_related("author").order_by("position", "id"),
        ),
        Prefetch(
            "book_catalog_tags",
            queryset=BookCatalogTag.objects.select_related("catalog_tag").order_by(
                "catalog_tag__sort_name",
                "catalog_tag__name",
                "id",
            ),
        ),
    )


class BookListView(ListAPIView):
    serializer_class = BookListSerializer

    def get_queryset(self):
        queryset = visible_books_for_user(self.request.user, cached=True)
        queryset = book_browse_queryset(queryset)
        queryset = apply_book_filters(queryset, self.request.query_params)
        return apply_book_ordering(queryset, parse_book_ordering(self.request))


class BookDetailView(RetrieveAPIView):
    serializer_class = BookDetailSerializer
    lookup_url_kwarg = "book_id"

    def get_queryset(self):
        queryset = visible_books_for_user(self.request.user, cached=False)
        return book_browse_queryset(queryset)
