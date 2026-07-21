from __future__ import annotations

from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.roles import is_librarian, is_manager
from library.groups.api_access import groups_available_via_api
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
        group = (
            groups_available_via_api(visible_groups_for_user(self.request.user))
            .filter(pk=self.kwargs[self.group_url_kwarg])
            .first()
        )
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
        group = self.get_group()
        if not is_manager(request.user):
            raise PermissionDenied("Not allowed to manage group memberships.")

        serializer = MembershipCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        profile = UserProfile.objects.select_related("user").get(
            pk=serializer.validated_data["user_id"]
        )
        try:
            membership = add_user_to_group(
                user=profile.user,
                group=group,
                is_curator=serializer.validated_data.get("is_curator", False),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise _membership_validation_error(exc) from exc
        if "role" in serializer.validated_data:
            _update_user_role(profile, serializer.validated_data["role"])
        membership.refresh_from_db()
        out = self.get_serializer(membership)
        return Response(out.data, status=status.HTTP_201_CREATED)


class LibraryGroupMembershipDetailView(GenericAPIView):
    serializer_class = LibraryGroupMembershipSerializer
    group_url_kwarg = "group_id"
    user_url_kwarg = "user_id"

    def get_group(self):
        group = (
            groups_available_via_api(visible_groups_for_user(self.request.user))
            .filter(pk=self.kwargs[self.group_url_kwarg])
            .first()
        )
        if group is None:
            raise Http404
        return group

    def get_membership(self):
        group = self.get_group()
        try:
            profile = UserProfile.objects.select_related("user").get(
                pk=self.kwargs[self.user_url_kwarg]
            )
        except UserProfile.DoesNotExist as exc:
            raise Http404 from exc
        membership = (
            LibraryGroupMembership.objects.filter(group=group, user=profile.user)
            .select_related("user", "user__profile", "group")
            .first()
        )
        if membership is None:
            raise Http404
        return membership

    def patch(self, request, *args, **kwargs):
        self.get_group()
        if not is_manager(request.user):
            raise PermissionDenied("Not allowed to manage group memberships.")
        membership = self.get_membership()
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
        if "role" in serializer.validated_data:
            _update_user_role(membership.user.profile, serializer.validated_data["role"])
        membership.refresh_from_db()
        out = self.get_serializer(membership)
        return Response(out.data)

    def delete(self, request, *args, **kwargs):
        group = self.get_group()
        if not is_manager(request.user):
            raise PermissionDenied("Not allowed to manage group memberships.")
        try:
            profile = UserProfile.objects.select_related("user").get(
                pk=self.kwargs[self.user_url_kwarg]
            )
        except UserProfile.DoesNotExist as exc:
            raise Http404 from exc
        remove_user_from_group(user=profile.user, group=group, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _update_user_role(profile: UserProfile, role: str) -> None:
    if profile.role != role:
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])


def _membership_validation_error(exc: DjangoValidationError) -> ValidationError:
    detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    return ValidationError(detail=detail)
