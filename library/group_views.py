from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core import policies
from core.errors import ErrorCode, api_error_response

from .catalog_serializers import BookSerializer
from .group_serializers import (
    BookGroupAssignmentSerializer,
    LibraryGroupCreateSerializer,
    LibraryGroupMembershipCreateSerializer,
    LibraryGroupMembershipPatchSerializer,
    LibraryGroupMembershipSerializer,
    LibraryGroupPresentationUpdateSerializer,
    LibraryGroupSerializer,
)
from .group_services import (
    add_book_to_group,
    add_user_to_group,
    delete_library_group,
    get_public_group,
    remove_book_from_group,
    remove_user_from_group,
    update_user_group_membership,
)
from .models import (
    Book,
    LibraryGroup,
    LibraryGroupMembership,
    is_public_group,
)
from .view_mixins import ClientBearerReadOnlyMixin

User = get_user_model()

class LibraryGroupViewSet(
    ClientBearerReadOnlyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}, "books": {"GET"}}
    queryset = LibraryGroup.objects.all()
    permission_classes = [IsAuthenticated]
    ordering = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return LibraryGroupCreateSerializer
        if self.action == "partial_update":
            return LibraryGroupPresentationUpdateSerializer
        return LibraryGroupSerializer

    def get_queryset(self):
        queryset = super().get_queryset().order_by(*self.ordering)
        user = self.request.user

        membership_qs = LibraryGroupMembership.objects.filter(user=user)
        queryset = queryset.prefetch_related(Prefetch("memberships", queryset=membership_qs))

        if policies.can_manage_library(user):
            return queryset

        public = get_public_group()
        return queryset.filter(
            Q(id=public.id) | Q(memberships__user=user)
        ).distinct()

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for presentation fields.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        if not policies.can_create_library_group(request.user):
            raise PermissionDenied("Not allowed.")

        serializer = self.get_serializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)

        group = LibraryGroup.objects.create(
            name=data["name"],
            description=data.get("description") or "",
        )
        out = LibraryGroupSerializer(group, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = LibraryGroupSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()
        # delete_library_group handles Public protection and permission checks.
        try:
            delete_library_group(actor=request.user, group=group)
        except ValidationError as exc:
            raise DRFValidationError(detail={"detail": str(exc)}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="books")
    def books(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()

        if request.method == "GET":
            if not policies.can_view_library_group(user=request.user, group=group):
                raise Http404()

            queryset = Book.objects.filter(group_assignments__group=group).distinct()
            if not policies.can_manage_library(request.user):
                accessible_ids = Book.objects.filter(
                    group_assignments__group__memberships__user=request.user
                ).values("id")
                queryset = queryset.filter(id__in=accessible_ids)

            page = self.paginate_queryset(queryset)
            serializer = BookSerializer(
                page if page is not None else queryset,
                many=True,
                context={"request": request},
            )
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        payload = request.data or {}
        book_id = payload.get("book")
        if not book_id:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing required field.",
                detail="Missing 'book'.",
                hint='POST JSON like {"book": "<book_id>"}',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if policies.can_manage_library(request.user):
            book_qs = Book.objects.all()
        else:
            if is_public_group(group):
                raise PermissionDenied("Not allowed.")
            if not policies.can_curate_group(user=request.user, group=group):
                raise PermissionDenied("Not allowed.")
            book_qs = Book.objects.filter(
                group_assignments__group__memberships__user=request.user
            ).distinct()

        try:
            book = book_qs.get(pk=book_id)
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        assignment = add_book_to_group(actor=request.user, book=book, group=group)
        serializer = BookGroupAssignmentSerializer(assignment, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"books/(?P<book_id>[^/.]+)")
    def remove_book(self, request, book_id: str | None = None, *args, **kwargs):
        group: LibraryGroup = self.get_object()
        if book_id is None:
            raise Http404()

        if policies.can_manage_library(request.user):
            book_qs = Book.objects.all()
        else:
            if is_public_group(group):
                raise PermissionDenied("Not allowed.")
            if not policies.can_curate_group(user=request.user, group=group):
                raise PermissionDenied("Not allowed.")
            book_qs = Book.objects.filter(group_assignments__group=group).distinct()

        try:
            book = book_qs.get(pk=book_id)
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        remove_book_from_group(actor=request.user, book=book, group=group)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="memberships")
    def memberships(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()

        if request.method == "GET":
            # Read permission: allow group members (and Public viewers) to see the
            # membership list, while keeping membership mutation Manager/Owner-only.
            #
            # Do not expose membership lists for groups the user cannot view.
            if not policies.can_view_library_group(user=request.user, group=group):
                raise Http404()

            if policies.can_manage_library(request.user):
                pass
            elif is_public_group(group):
                pass
            elif LibraryGroupMembership.objects.filter(user=request.user, group=group).exists():
                pass
            else:
                raise Http404()

            qs = (
                LibraryGroupMembership.objects.select_related("user")
                .filter(group=group)
                .order_by("user__username", "id")
            )
            page = self.paginate_queryset(qs)
            memberships = list(page) if page is not None else list(qs)
            payload = []
            for membership in memberships:
                user = membership.user
                payload.append(
                    {
                        "id": membership.id,
                        "user_id": user.pk,
                        "username": user.get_username(),
                        "email": user.email or "",
                        "role": membership.role,
                        "is_owner": policies.is_owner(user),
                        "created_at": membership.created_at,
                        "updated_at": membership.updated_at,
                    }
                )
            serializer = LibraryGroupMembershipSerializer(payload, many=True)
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")

        create = LibraryGroupMembershipCreateSerializer(data=request.data or {})
        create.is_valid(raise_exception=True)
        data = create.validated_data

        user_id = data.get("user")
        role = data.get("role")
        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="User not found.",
                detail=f"No user with id={user_id}.",
                hint="Use a valid user id from /api/v1/accounts/users/.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = add_user_to_group(
                actor=request.user, target_user=target, group=group, role=role
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership request.",
                detail=str(exc),
                hint="Use role=reader|curator (curator only for non-Public groups).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = membership.user
        payload = {
            "id": membership.id,
            "user_id": user.pk,
            "username": user.get_username(),
            "email": user.email or "",
            "role": membership.role,
            "is_owner": policies.is_owner(user),
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        }
        serializer = LibraryGroupMembershipSerializer(payload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"memberships/(?P<membership_id>[^/.]+)",
    )
    def membership_detail(
        self, request, membership_id: str | None = None, *args, **kwargs
    ):
        group: LibraryGroup = self.get_object()
        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")
        if membership_id is None:
            raise Http404()

        try:
            membership = LibraryGroupMembership.objects.select_related("user").get(
                pk=membership_id, group=group
            )
        except LibraryGroupMembership.DoesNotExist as exc:
            raise Http404() from exc

        if request.method == "DELETE":
            remove_user_from_group(actor=request.user, membership=membership)
            return Response(status=status.HTTP_204_NO_CONTENT)

        patch = LibraryGroupMembershipPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = patch.validated_data

        try:
            membership = update_user_group_membership(
                actor=request.user, membership=membership, role=data["role"]
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership update.",
                detail=str(exc),
                hint="Use role=reader|curator (curator only for non-Public groups).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = membership.user
        payload = {
            "id": membership.id,
            "user_id": user.pk,
            "username": user.get_username(),
            "email": user.email or "",
            "role": membership.role,
            "is_owner": policies.is_owner(user),
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        }
        serializer = LibraryGroupMembershipSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
