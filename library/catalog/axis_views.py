from __future__ import annotations

from functools import cached_property

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
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
    AuthorCreateSerializer,
    AuthorAxisUpdateSerializer,
    CatalogTagAxisSerializer,
    SeriesAxisSerializer,
    SeriesCreateSerializer,
    SeriesAxisUpdateSerializer,
)
from library.catalog.axis_services import (
    CatalogEntityInUseError,
    create_author,
    create_series,
    delete_author,
    delete_series,
    update_author,
    update_series,
)
from library.catalog.filters import apply_catalog_tag_filter
from library.catalog.preview_books import (
    attach_author_preview_books,
    attach_series_preview_books,
    parse_preview_book_limit,
)
from library.models import Author, Series
from library.queries import visible_books_for_user


def is_session_catalog_manager(request) -> bool:
    return isinstance(
        request.successful_authenticator, SessionAuthentication
    ) and is_librarian(request.user)


class _BaseAxisMixin(LibraryBearerReadMixin):
    lookup_url_kwarg = "axis_id"
    search_normalized_name = False
    supports_exclude_id = False

    def visible_books(self):
        return visible_books_for_user(self.request.user, cached=self.use_cached_visibility)

    def axis_queryset(self):
        raise NotImplementedError

    def has_catalog_tag_filter(self) -> bool:
        return bool((self.request.query_params.get("tag") or "").strip())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = self.preview_book_limit is not None
        return context

    @cached_property
    def preview_book_limit(self) -> int | None:
        return parse_preview_book_limit(self.request)

    def preview_books_queryset(self):
        return apply_catalog_tag_filter(self.visible_books(), self.request.query_params)

    def attach_preview_books(self, parents, *, limit):
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
        if self.supports_exclude_id:
            queryset = self.exclude_axis_id(queryset)
        return apply_axis_ordering(queryset, parse_axis_ordering(self.request))

    def exclude_axis_id(self, queryset):
        values = self.request.query_params.getlist("exclude_id")
        if not values:
            return queryset
        raw = values[0].strip() if len(values) == 1 else ""
        if not raw:
            raise serializers.ValidationError({"exclude_id": "Invalid id."})
        try:
            axis_id = queryset.model._meta.pk.to_python(raw)
        except (DjangoValidationError, TypeError, ValueError) as exc:
            raise serializers.ValidationError({"exclude_id": "Invalid id."}) from exc
        return queryset.exclude(pk=axis_id)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            if self.preview_book_limit is not None:
                self.attach_preview_books(page, limit=self.preview_book_limit)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        rows = list(queryset)
        if self.preview_book_limit is not None:
            self.attach_preview_books(rows, limit=self.preview_book_limit)
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)


class _BaseAxisDetailView(_BaseAxisMixin, RetrieveAPIView):
    use_cached_visibility = False

    def get_queryset(self):
        return self.axis_queryset()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.preview_book_limit is not None:
            self.attach_preview_books([instance], limit=self.preview_book_limit)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        instance = self.get_object()
        serializer = self.update_serializer_class(data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            self.update_axis(instance, serializer.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        refreshed = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(refreshed).data)


class AuthorAxisMixin(_BaseAxisMixin):
    serializer_class = AuthorAxisSerializer
    search_normalized_name = True
    supports_exclude_id = True

    def axis_queryset(self):
        if is_session_catalog_manager(self.request) and not self.has_catalog_tag_filter():
            return Author.objects.annotate(book_count=Count("book_authors__book", distinct=True))
        visible_books = apply_catalog_tag_filter(self.visible_books(), self.request.query_params)
        return visible_authors_from_books(visible_books)

    def attach_preview_books(self, parents, *, limit):
        attach_author_preview_books(
            authors=parents,
            visible_books=self.preview_books_queryset(),
            limit=limit,
        )


class AuthorListView(AuthorAxisMixin, _BaseAxisListView):
    def post(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        serializer = AuthorCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            author = create_author(
                name=serializer.validated_data["name"],
                sort_name=serializer.validated_data.get("sort_name", ""),
                biography=serializer.validated_data.get("biography", ""),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        author.book_count = 0
        response_serializer = AuthorAxisSerializer(author, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AuthorDetailView(AuthorAxisMixin, _BaseAxisDetailView):
    update_serializer_class = AuthorAxisUpdateSerializer

    def update_axis(self, instance, data):
        update_author(author=instance, fields=data)

    def delete(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        author = self.get_object()
        try:
            delete_author(author=author)
        except CatalogEntityInUseError as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": str(exc),
                        "details": {"book_count": exc.attached_book_count},
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SeriesAxisMixin(_BaseAxisMixin):
    serializer_class = SeriesAxisSerializer
    search_normalized_name = True
    supports_exclude_id = True

    def axis_queryset(self):
        if is_session_catalog_manager(self.request) and not self.has_catalog_tag_filter():
            return Series.objects.annotate(book_count=Count("book_series__book", distinct=True))
        visible_books = apply_catalog_tag_filter(self.visible_books(), self.request.query_params)
        return visible_series_from_books(visible_books)

    def attach_preview_books(self, parents, *, limit):
        attach_series_preview_books(
            series=parents,
            visible_books=self.preview_books_queryset(),
            limit=limit,
        )


class SeriesListView(SeriesAxisMixin, _BaseAxisListView):
    def post(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        serializer = SeriesCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            series = create_series(**serializer.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        series.book_count = 0
        response_serializer = SeriesAxisSerializer(series, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class SeriesDetailView(SeriesAxisMixin, _BaseAxisDetailView):
    update_serializer_class = SeriesAxisUpdateSerializer

    def update_axis(self, instance, data):
        update_series(series=instance, fields=data)

    def delete(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed.")
        series = self.get_object()
        try:
            delete_series(series=series)
        except CatalogEntityInUseError as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": str(exc),
                        "details": {"book_count": exc.attached_book_count},
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CatalogTagAxisMixin(_BaseAxisMixin):
    serializer_class = CatalogTagAxisSerializer
    search_normalized_name = True

    def axis_queryset(self):
        return visible_tags_from_books(self.visible_books())


class CatalogTagListView(CatalogTagAxisMixin, _BaseAxisListView):
    pass


class CatalogTagDetailView(CatalogTagAxisMixin, _BaseAxisDetailView):
    http_method_names = ["get", "head", "options"]
