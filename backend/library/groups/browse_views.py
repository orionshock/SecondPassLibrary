from __future__ import annotations

from functools import cached_property
from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from library.api_access import LibraryBearerReadMixin
from library.catalog.axes import (
    apply_axis_filters,
    apply_axis_ordering,
    parse_axis_ordering,
    visible_authors_from_books,
    visible_series_from_books,
    visible_tags_from_books,
)
from library.catalog.book_list_response import CatalogTagAggregateBookListMixin
from library.catalog.book_queries import book_browse_queryset, book_search_queryset
from library.catalog.filters import apply_catalog_tag_filter
from library.catalog.ordering import (
    BOOK_SEARCH_ORDERINGS,
    parse_book_ordering,
    parse_ordering_param,
)
from library.catalog.preview_books import (
    attach_author_preview_books,
    attach_series_preview_books,
    parse_preview_book_limit,
)
from library.catalog.serializers.axes import (
    AuthorAxisSerializer,
    CatalogTagAxisSerializer,
    SeriesAxisSerializer,
)
from library.catalog.serializers.books import BookListSerializer
from library.catalog.tag_aggregates import catalog_tag_aggregates
from library.models import LibraryGroup
from library.queries import group_is_visible_to_user, visible_books_for_group
from shelves.models import Shelf
from shelves.querysets import filter_readable_shelves, with_visible_item_count


class GroupBrowseMixin(LibraryBearerReadMixin):
    group_url_kwarg = "group_id"

    def get_group(self) -> LibraryGroup:
        group = get_object_or_404(
            LibraryGroup.objects.all(),
            pk=self.kwargs[self.group_url_kwarg],
        )
        if not group_is_visible_to_user(user=self.request.user, group=group):
            raise Http404
        return group

    def visible_group_books(self):
        return visible_books_for_group(self.request.user, self.get_group(), cached=True)


class GroupBookListView(
    CatalogTagAggregateBookListMixin, GroupBrowseMixin, ListAPIView
):
    serializer_class = BookListSerializer

    def get_queryset(self):
        group = self.get_group()
        queryset = visible_books_for_group(self.request.user, group, cached=True)
        queryset = _exclude_group_shelf_books(
            queryset,
            user=self.request.user,
            group=group,
            raw_shelf_id=self.request.query_params.get("exclude_shelf"),
        )
        return book_browse_queryset(
            queryset,
            query_params=self.request.query_params,
            ordering=parse_book_ordering(self.request),
        )


class GroupBookSearchView(
    CatalogTagAggregateBookListMixin, GroupBrowseMixin, ListAPIView
):
    serializer_class = BookListSerializer

    def get_queryset(self):
        group = self.get_group()
        queryset = visible_books_for_group(self.request.user, group, cached=False)
        queryset = _exclude_group_shelf_books(
            queryset,
            user=self.request.user,
            group=group,
            raw_shelf_id=self.request.query_params.get("exclude_shelf"),
        )
        return book_search_queryset(
            queryset,
            term=str(self.request.query_params.get("q") or "").strip(),
            query_params=self.request.query_params,
            ordering=parse_ordering_param(
                self.request,
                allowed=BOOK_SEARCH_ORDERINGS,
                default="title",
            ),
        )


def _exclude_group_shelf_books(queryset, *, user, group, raw_shelf_id):
    if raw_shelf_id is None:
        return queryset

    try:
        shelf_id = UUID(str(raw_shelf_id).strip())
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError({"exclude_shelf": "Must be a valid UUID."}) from exc

    shelves = with_visible_item_count(
        Shelf.objects.select_related("owner_group", "owner_user"),
        user=user,
    )
    shelf = filter_readable_shelves(shelves, user=user).filter(pk=shelf_id).first()
    if shelf is None:
        raise Http404
    if shelf.owner_type != Shelf.OWNER_TYPE_GROUP or shelf.owner_group_id != group.id:
        raise Http404
    return queryset.exclude(shelf_items__shelf=shelf)


class GroupAxisListMixin(GroupBrowseMixin, ListAPIView):
    search_normalized_name = False
    supports_exclude_id = False
    supports_preview_books = False
    includes_catalog_tag_aggregates = True

    def axis_queryset(self):
        raise NotImplementedError

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = self.preview_book_limit is not None
        return context

    @cached_property
    def preview_book_limit(self) -> int | None:
        if not self.supports_preview_books:
            return None
        return parse_preview_book_limit(self.request)

    def attach_preview_books(self, parents, *, limit):
        return None

    def catalog_tag_books(self, filtered_axes):
        raise NotImplementedError

    def get_queryset(self):
        queryset = self.axis_queryset()
        queryset = apply_axis_filters(
            queryset,
            self.request.query_params,
            include_normalized=self.search_normalized_name,
            supports_exclude_id=self.supports_exclude_id,
        )
        return apply_axis_ordering(queryset, parse_axis_ordering(self.request))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not self.includes_catalog_tag_aggregates:
            return self._list_without_catalog_tag_aggregates(queryset)
        catalog_tags = CatalogTagAxisSerializer(
            catalog_tag_aggregates(self.catalog_tag_books(queryset)), many=True
        ).data
        page = self.paginate_queryset(queryset)
        if page is not None:
            if self.preview_book_limit is not None:
                self.attach_preview_books(page, limit=self.preview_book_limit)
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["catalog_tags"] = catalog_tags
            return response

        rows = list(queryset)
        if self.preview_book_limit is not None:
            self.attach_preview_books(rows, limit=self.preview_book_limit)
        serializer = self.get_serializer(rows, many=True)
        return Response({"catalog_tags": catalog_tags, "results": serializer.data})

    def _list_without_catalog_tag_aggregates(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
        return Response(self.get_serializer(queryset, many=True).data)


class GroupAuthorListView(GroupAxisListMixin):
    serializer_class = AuthorAxisSerializer
    search_normalized_name = True
    supports_exclude_id = True
    supports_preview_books = True

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        )
        return visible_authors_from_books(visible_books)

    def attach_preview_books(self, parents, *, limit):
        attach_author_preview_books(
            authors=parents,
            visible_books=apply_catalog_tag_filter(
                self.visible_group_books(), self.request.query_params
            ),
            limit=limit,
        )

    def catalog_tag_books(self, filtered_axes):
        return apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        ).filter(book_authors__author__in=filtered_axes).distinct()


class GroupSeriesListView(GroupAxisListMixin):
    serializer_class = SeriesAxisSerializer
    search_normalized_name = True
    supports_exclude_id = True
    supports_preview_books = True

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        )
        return visible_series_from_books(visible_books)

    def attach_preview_books(self, parents, *, limit):
        attach_series_preview_books(
            series=parents,
            visible_books=apply_catalog_tag_filter(
                self.visible_group_books(), self.request.query_params
            ),
            limit=limit,
        )

    def catalog_tag_books(self, filtered_axes):
        return apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        ).filter(book_series__series__in=filtered_axes).distinct()


class GroupCatalogTagListView(GroupAxisListMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True
    includes_catalog_tag_aggregates = False

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_group_books())
