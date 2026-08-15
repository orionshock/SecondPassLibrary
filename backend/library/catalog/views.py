from __future__ import annotations

from django.db.models import Prefetch
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response

from accounts.roles import is_librarian
from library.api_access import LibraryBearerReadMixin
from library.catalog.edit_services import update_book_metadata
from library.catalog.filters import apply_book_filters
from library.catalog.ordering import apply_book_ordering, parse_book_ordering
from library.catalog.serializers.books import (
    BookDetailSerializer,
    BookListSerializer,
    BookUpdateSerializer,
)
from library.groups.book_filters import exclude_books_assigned_to_group
from library.models import BookAuthor, BookCatalogTag
from library.queries import visible_books_for_user, visible_groups_for_user


def book_row_queryset(queryset):
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


def book_detail_queryset(queryset):
    return book_row_queryset(queryset).prefetch_related("identifiers")


def attach_visible_groups_to_book(*, book, user):
    book._visible_groups = list(
        visible_groups_for_user(user)
        .filter(book_assignments__book=book)
        .order_by("name", "id")
    )
    return book


class BookListView(LibraryBearerReadMixin, ListAPIView):
    serializer_class = BookListSerializer

    def get_queryset(self):
        queryset = visible_books_for_user(self.request.user, cached=True)
        queryset = exclude_books_assigned_to_group(
            queryset,
            user=self.request.user,
            raw_group_id=self.request.query_params.get("exclude_group", ""),
        )
        queryset = book_row_queryset(queryset)
        queryset = apply_book_filters(queryset, self.request.query_params)
        return apply_book_ordering(queryset, parse_book_ordering(self.request))


class BookDetailView(LibraryBearerReadMixin, RetrieveUpdateAPIView):
    serializer_class = BookDetailSerializer
    lookup_url_kwarg = "book_id"

    def get_queryset(self):
        queryset = visible_books_for_user(self.request.user, cached=False)
        return book_detail_queryset(queryset)

    def retrieve(self, request, *args, **kwargs):
        book = attach_visible_groups_to_book(book=self.get_object(), user=request.user)
        return Response(self.get_serializer(book).data)

    def partial_update(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        book = self.get_object()
        serializer = BookUpdateSerializer(
            data=request.data or {},
            partial=True,
            context={"book": book},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        authors = data.pop("authors", None)
        series_supplied = "series" in data
        series = data.pop("series", None)
        series_index_supplied = "series_index" in data
        series_index = data.pop("series_index", None)
        identifiers = data.pop("identifiers", None)
        catalog_tags = data.pop("catalog_tags", None)
        try:
            update_book_metadata(
                book=book,
                scalar_fields=data,
                authors=authors,
                series=series,
                series_supplied=series_supplied,
                series_index=series_index,
                series_index_supplied=series_index_supplied,
                identifiers=identifiers,
                catalog_tags=catalog_tags,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        refreshed = attach_visible_groups_to_book(
            book=self.get_queryset().get(pk=book.pk), user=request.user
        )
        return Response(BookDetailSerializer(refreshed, context={"request": request}).data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
