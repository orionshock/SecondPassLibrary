from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from library import policies
from library.groups.public_group import is_public_group
from library.groups.querysets import (
    apply_group_ordering,
    apply_group_search,
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
from library.queries import visible_groups_for_user


class LibraryGroupListView(ListAPIView):
    serializer_class = LibraryGroupSerializer

    def get_queryset(self):
        queryset = visible_groups_for_user(self.request.user)
        queryset = apply_group_search(queryset, self.request.query_params)
        return apply_group_ordering(queryset, parse_group_ordering(self.request))

    def post(self, request, *args, **kwargs):
        if not policies.can_create_library_group(request.user):
            raise PermissionDenied("Not allowed to create library groups.")

        serializer = LibraryGroupCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        group = create_library_group(**serializer.validated_data)
        out = self.get_serializer(group)
        return Response(out.data, status=status.HTTP_201_CREATED)


class LibraryGroupDetailView(RetrieveAPIView):
    serializer_class = LibraryGroupSerializer
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return visible_groups_for_user(self.request.user)

    def patch(self, request, *args, **kwargs):
        group = self.get_object()
        if not policies.can_manage_group_identity(user=request.user, group=group):
            raise PermissionDenied("Not allowed to update this library group.")

        serializer = LibraryGroupPatchSerializer(data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            group = update_library_group(group=group, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise _drf_validation_error(exc) from exc
        out = self.get_serializer(group)
        return Response(out.data)

    def delete(self, request, *args, **kwargs):
        group = self.get_object()
        if is_public_group(group):
            raise _drf_validation_error("Public/Common Room group cannot be deleted.")
        if not policies.can_delete_library_group(request.user, group):
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
