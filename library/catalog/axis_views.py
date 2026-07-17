from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from accounts.roles import is_librarian

from library.api_access import LibraryBearerReadMixin
from library.catalog.axes import (
    apply_axis_ordering,
    apply_axis_search,
    parse_axis_ordering,
    visible_authors_from_books,
    visible_series_from_books,
    visible_tags_from_books,
)
from library.catalog.serializers import (
    AuthorAxisSerializer,
    AuthorAxisUpdateSerializer,
    CatalogTagAxisSerializer,
    SeriesAxisSerializer,
    SeriesAxisUpdateSerializer,
)
from library.catalog.axis_services import update_author, update_series
from library.catalog.filters import apply_catalog_tag_filter
from library.catalog.preview_books import (
    attach_author_preview_books,
    attach_series_preview_books,
    include_preview_books,
)
from library.queries import visible_books_for_user


class _BaseAxisMixin(LibraryBearerReadMixin):
    lookup_url_kwarg = "axis_id"
    search_normalized_name = False

    def visible_books(self):
        return visible_books_for_user(self.request.user, cached=self.use_cached_visibility)

    def axis_queryset(self):
        raise NotImplementedError

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

    def preview_books_queryset(self):
        return apply_catalog_tag_filter(self.visible_books(), self.request.query_params)

    def attach_preview_books(self, parents):
        return None


class _BaseAxisListView(_BaseAxisMixin, ListAPIView):
    use_cached_visibility = True

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


class _BaseAxisDetailView(_BaseAxisMixin, RetrieveAPIView):
    use_cached_visibility = False

    def get_queryset(self):
        return self.axis_queryset()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if include_preview_books(request):
            self.attach_preview_books([instance])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        instance = self.get_object()
        serializer = self.update_serializer_class(data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.update_axis(instance, serializer.validated_data)
        refreshed = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(refreshed).data)


class AuthorAxisMixin(_BaseAxisMixin):
    serializer_class = AuthorAxisSerializer

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(self.visible_books(), self.request.query_params)
        return visible_authors_from_books(visible_books)

    def attach_preview_books(self, parents):
        attach_author_preview_books(
            authors=parents,
            visible_books=self.preview_books_queryset(),
        )


class AuthorListView(AuthorAxisMixin, _BaseAxisListView):
    pass


class AuthorDetailView(AuthorAxisMixin, _BaseAxisDetailView):
    update_serializer_class = AuthorAxisUpdateSerializer

    def update_axis(self, instance, data):
        update_author(author=instance, fields=data)


class SeriesAxisMixin(_BaseAxisMixin):
    serializer_class = SeriesAxisSerializer

    def axis_queryset(self):
        visible_books = apply_catalog_tag_filter(self.visible_books(), self.request.query_params)
        return visible_series_from_books(visible_books)

    def attach_preview_books(self, parents):
        attach_series_preview_books(
            series=parents,
            visible_books=self.preview_books_queryset(),
        )


class SeriesListView(SeriesAxisMixin, _BaseAxisListView):
    pass


class SeriesDetailView(SeriesAxisMixin, _BaseAxisDetailView):
    update_serializer_class = SeriesAxisUpdateSerializer

    def update_axis(self, instance, data):
        update_series(series=instance, fields=data)


class CatalogTagAxisMixin(_BaseAxisMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_books())


class CatalogTagListView(CatalogTagAxisMixin, _BaseAxisListView):
    pass


class CatalogTagDetailView(CatalogTagAxisMixin, _BaseAxisDetailView):
    http_method_names = ["get", "head", "options"]
