from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from library.api_access import LibraryBearerReadMixin
from library.catalog.axes import (
    apply_axis_ordering,
    apply_axis_search,
    parse_axis_ordering,
    visible_authors_from_books,
    visible_series_from_books,
    visible_tags_from_books,
)
from library.catalog.filters import apply_book_filters, apply_catalog_tag_filter
from library.catalog.ordering import apply_book_ordering, parse_book_ordering
from library.catalog.preview_books import (
    attach_author_preview_books,
    attach_series_preview_books,
    include_preview_books,
)
from library.catalog.serializers import (
    AuthorAxisSerializer,
    BookListSerializer,
    CatalogTagAxisSerializer,
    SeriesAxisSerializer,
)
from library.catalog.views import book_browse_queryset
from library.groups.api_access import groups_available_via_api
from library.models import LibraryGroup
from library.queries import group_is_visible_to_user, visible_books_for_group


class GroupBrowseMixin(LibraryBearerReadMixin):
    group_url_kwarg = "group_id"

    def get_group(self) -> LibraryGroup:
        group = get_object_or_404(
            groups_available_via_api(LibraryGroup.objects.all()),
            pk=self.kwargs[self.group_url_kwarg],
        )
        if not group_is_visible_to_user(user=self.request.user, group=group):
            raise Http404
        return group

    def visible_group_books(self):
        return visible_books_for_group(self.request.user, self.get_group(), cached=True)


class GroupBookListView(GroupBrowseMixin, ListAPIView):
    serializer_class = BookListSerializer

    def get_queryset(self):
        queryset = book_browse_queryset(self.visible_group_books())
        queryset = apply_book_filters(queryset, self.request.query_params)
        return apply_book_ordering(queryset, parse_book_ordering(self.request))


class GroupAxisListMixin(GroupBrowseMixin, ListAPIView):
    search_normalized_name = False

    def axis_queryset(self):
        raise NotImplementedError

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

    def attach_preview_books(self, parents):
        return None

    def get_queryset(self):
        queryset = self.axis_queryset()
        queryset = apply_axis_search(
            queryset,
            self.request.query_params,
            include_normalized=self.search_normalized_name,
        )
        return apply_axis_ordering(queryset, parse_axis_ordering(self.request))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            if include_preview_books(request):
                self.attach_preview_books(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        rows = list(queryset)
        if include_preview_books(request):
            self.attach_preview_books(rows)
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)


class GroupAuthorListView(GroupAxisListMixin):
    serializer_class = AuthorAxisSerializer

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        )
        return visible_authors_from_books(visible_books)

    def attach_preview_books(self, parents):
        attach_author_preview_books(
            authors=parents,
            visible_books=apply_catalog_tag_filter(
                self.visible_group_books(), self.request.query_params
            ),
        )


class GroupSeriesListView(GroupAxisListMixin):
    serializer_class = SeriesAxisSerializer

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(
            self.visible_group_books(), self.request.query_params
        )
        return visible_series_from_books(visible_books)

    def attach_preview_books(self, parents):
        attach_series_preview_books(
            series=parents,
            visible_books=apply_catalog_tag_filter(
                self.visible_group_books(), self.request.query_params
            ),
        )


class GroupCatalogTagListView(GroupAxisListMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_group_books())
