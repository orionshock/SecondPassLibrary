from __future__ import annotations

from rest_framework.generics import ListAPIView, RetrieveAPIView

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
    CatalogTagAxisSerializer,
    SeriesAxisSerializer,
)
from library.queries import visible_books_for_user


class _BaseAxisMixin:
    lookup_url_kwarg = "axis_id"
    search_normalized_name = False

    def visible_books(self):
        return visible_books_for_user(self.request.user, cached=self.use_cached_visibility)

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


class _BaseAxisListView(_BaseAxisMixin, ListAPIView):
    use_cached_visibility = True


class _BaseAxisDetailView(_BaseAxisMixin, RetrieveAPIView):
    use_cached_visibility = False


class AuthorAxisMixin(_BaseAxisMixin):
    serializer_class = AuthorAxisSerializer

    def axis_queryset(self):
        return visible_authors_from_books(self.visible_books())


class AuthorListView(AuthorAxisMixin, _BaseAxisListView):
    pass


class AuthorDetailView(AuthorAxisMixin, _BaseAxisDetailView):
    pass


class SeriesAxisMixin(_BaseAxisMixin):
    serializer_class = SeriesAxisSerializer

    def axis_queryset(self):
        return visible_series_from_books(self.visible_books())


class SeriesListView(SeriesAxisMixin, _BaseAxisListView):
    pass


class SeriesDetailView(SeriesAxisMixin, _BaseAxisDetailView):
    pass


class CatalogTagAxisMixin(_BaseAxisMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_books())


class CatalogTagListView(CatalogTagAxisMixin, _BaseAxisListView):
    pass


class CatalogTagDetailView(CatalogTagAxisMixin, _BaseAxisDetailView):
    pass
