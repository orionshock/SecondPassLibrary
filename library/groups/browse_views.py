from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView

from library.catalog.axes import (
    apply_axis_ordering,
    apply_axis_search,
    parse_axis_ordering,
    visible_authors_from_books,
    visible_series_from_books,
    visible_tags_from_books,
)
from library.catalog.filters import apply_book_filters
from library.catalog.ordering import apply_book_ordering, parse_book_ordering
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


class GroupBrowseMixin:
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

    def get_queryset(self):
        queryset = self.axis_queryset()
        queryset = apply_axis_search(
            queryset,
            self.request.query_params,
            include_normalized=self.search_normalized_name,
        )
        return apply_axis_ordering(queryset, parse_axis_ordering(self.request))


class GroupAuthorListView(GroupAxisListMixin):
    serializer_class = AuthorAxisSerializer

    def axis_queryset(self):
        return visible_authors_from_books(self.visible_group_books())


class GroupSeriesListView(GroupAxisListMixin):
    serializer_class = SeriesAxisSerializer

    def axis_queryset(self):
        return visible_series_from_books(self.visible_group_books())


class GroupCatalogTagListView(GroupAxisListMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_group_books())
