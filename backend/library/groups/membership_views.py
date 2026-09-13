from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.roles import is_librarian
from library.groups.api_access import (
    authorize_membership_mutation,
    normal_mutation_group_or_404,
)
from library.groups.membership_serializers import (
    LibraryGroupMembershipSerializer,
    MembershipCreateSerializer,
    MembershipPatchSerializer,
)
from library.groups.memberships import (
    add_user_to_group,
    remove_user_from_group,
    set_group_membership_curator,
)
from library.models import LibraryGroupMembership
from library.queries import visible_groups_for_user


class LibraryGroupMembershipListView(GenericAPIView):
    serializer_class = LibraryGroupMembershipSerializer
    group_url_kwarg = "group_id"

    def get_group(self):
        group = visible_groups_for_user(self.request.user).filter(
            pk=self.kwargs[self.group_url_kwarg]
        ).first()
        if group is None:
            raise Http404
        return group

    def get_queryset(self):
        group = self.get_group()
        return (
            LibraryGroupMembership.objects.filter(group=group)
            .select_related("user", "user__profile", "group")
            .order_by("user__username", "id")
        )

    def get(self, request, *args, **kwargs):
        group = self.get_group()
        if not is_librarian(request.user) and not group.memberships.filter(
            user=request.user
        ).exists():
            raise PermissionDenied("Not allowed to view group memberships.")
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        group = normal_mutation_group_or_404(
            actor=request.user,
            group_id=self.kwargs[self.group_url_kwarg],
        )
        access = authorize_membership_mutation(actor=request.user, group=group)

        serializer = MembershipCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        target_user = access.target_user_or_404(
            profile_id=serializer.validated_data["user_id"]
        )
        try:
            membership = add_user_to_group(
                user=target_user,
                group=group,
                is_curator=serializer.validated_data.get("is_curator", False),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise _membership_validation_error(exc) from exc
        membership.refresh_from_db()
        out = self.get_serializer(membership)
        return Response(out.data, status=status.HTTP_201_CREATED)


class LibraryGroupMembershipDetailView(GenericAPIView):
    serializer_class = LibraryGroupMembershipSerializer
    group_url_kwarg = "group_id"
    user_url_kwarg = "user_id"

    def get_group(self):
        return normal_mutation_group_or_404(
            actor=self.request.user,
            group_id=self.kwargs[self.group_url_kwarg],
        )

    def patch(self, request, *args, **kwargs):
        group = self.get_group()
        access = authorize_membership_mutation(actor=request.user, group=group)
        membership = access.membership_for_update(
            profile_id=self.kwargs[self.user_url_kwarg]
        )
        serializer = MembershipPatchSerializer(data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)

        if "is_curator" in serializer.validated_data:
            try:
                set_group_membership_curator(
                    membership=membership,
                    is_curator=serializer.validated_data["is_curator"],
                    actor=request.user,
                )
            except DjangoValidationError as exc:
                raise _membership_validation_error(exc) from exc
        membership.refresh_from_db()
        out = self.get_serializer(membership)
        return Response(out.data)

    def delete(self, request, *args, **kwargs):
        group = self.get_group()
        access = authorize_membership_mutation(actor=request.user, group=group)
        target_user = access.target_user_or_404(
            profile_id=self.kwargs[self.user_url_kwarg]
        )
        remove_user_from_group(user=target_user, group=group, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _membership_validation_error(exc: DjangoValidationError) -> ValidationError:
    detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    return ValidationError(detail=detail)
