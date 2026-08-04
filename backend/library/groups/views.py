from __future__ import annotations

from functools import cached_property

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from accounts.roles import is_manager
from library.api_access import LibraryBearerReadMixin
from library.catalog.preview_books import parse_preview_book_limit
from library.groups.api_access import (
    require_group_creation_available,
    require_group_mutation_available,
)
from library.groups.public_group import is_public_group
from library.groups.querysets import (
    apply_group_ordering,
    apply_group_search,
    filter_groups_by_book,
    parse_group_ordering,
)
from library.groups.serializers import (
    LibraryGroupCreateSerializer,
    LibraryGroupPatchSerializer,
    LibraryGroupSerializer,
)
from library.groups.services import (
    create_library_group,
    delete_library_group,
    update_library_group,
)
from library.queries import visible_books_for_group, visible_groups_for_user
from library.roles import is_curator


def _attach_group_preview_books(*, groups, user, limit: int) -> None:
    for group in groups:
        group._preview_books = list(
            visible_books_for_group(user, group, cached=True).order_by(
                "sort_title", "title", "id"
            )[:limit]
        )


class GroupPreviewBooksMixin:
    @cached_property
    def preview_book_limit(self) -> int | None:
        if self.request.method != "GET":
            return None
        return parse_preview_book_limit(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = self.preview_book_limit is not None
        return context


class LibraryGroupListView(LibraryBearerReadMixin, GroupPreviewBooksMixin, ListAPIView):
    serializer_class = LibraryGroupSerializer

    def get_queryset(self):
        queryset = visible_groups_for_user(self.request.user)
        queryset = filter_groups_by_book(queryset, self.request.query_params)
        queryset = apply_group_search(queryset, self.request.query_params)
        return apply_group_ordering(queryset, parse_group_ordering(self.request))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        groups = list(page) if page is not None else list(queryset)
        if self.preview_book_limit is not None:
            _attach_group_preview_books(
                groups=groups,
                user=request.user,
                limit=self.preview_book_limit,
            )
        serializer = self.get_serializer(groups, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        require_group_creation_available()
        if not is_manager(request.user):
            raise PermissionDenied("Not allowed to create library groups.")

        serializer = LibraryGroupCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            group = create_library_group(actor=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc
        out = self.get_serializer(group)
        return Response(out.data, status=status.HTTP_201_CREATED)


class LibraryGroupDetailView(LibraryBearerReadMixin, GroupPreviewBooksMixin, RetrieveAPIView):
    serializer_class = LibraryGroupSerializer
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return visible_groups_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        group = self.get_object()
        if self.preview_book_limit is not None:
            _attach_group_preview_books(
                groups=[group],
                user=request.user,
                limit=self.preview_book_limit,
            )
        return Response(self.get_serializer(group).data)

    def patch(self, request, *args, **kwargs):
        group = self.get_object()
        require_group_mutation_available(group)
        if is_public_group(group):
            raise PermissionDenied(
                "Public group identity is managed through Server Settings."
            )
        serializer = LibraryGroupPatchSerializer(
            group,
            data=request.data or {},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if serializer.changes_field("name") and not is_manager(request.user):
            raise PermissionDenied("Not allowed to rename this library group.")
        if serializer.changes_field("description") and not is_curator(
            request.user, group
        ):
            raise PermissionDenied("Not allowed to update this library group description.")
        try:
            group = update_library_group(
                group=group,
                actor=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc
        out = self.get_serializer(group)
        return Response(out.data)

    def delete(self, request, *args, **kwargs):
        group = self.get_object()
        require_group_mutation_available(group)
        if is_public_group(group):
            raise _drf_validation_error("Public/Common Room group cannot be deleted.")
        if not is_manager(request.user):
            raise PermissionDenied("Not allowed to delete this library group.")

        try:
            delete_library_group(group=group, actor=request.user)
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


def _drf_validation_error(exc):
    from rest_framework.exceptions import ValidationError

    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    else:
        detail = exc
    return ValidationError(detail)
