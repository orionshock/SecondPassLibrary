from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db.models import Exists, F, OuterRef, Prefetch, Q, Window
from django.db.models.functions import Random, RowNumber
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.services import get_or_create_profile
from library import policies
from core import server_settings
from core.errors import ErrorCode, api_error_response

from ..catalog.preview_books import (
    PREVIEW_BOOK_LIMIT,
    attach_preview_books_from_queryset,
    include_preview_books,
)
from ..catalog.serializers import BookSerializer
from .serializers import (
    BookGroupAssignmentSerializer,
    LibraryGroupCreateSerializer,
    LibraryGroupMembershipCreateSerializer,
    LibraryGroupMembershipPatchSerializer,
    LibraryGroupMembershipSerializer,
    LibraryGroupPresentationUpdateSerializer,
    LibraryGroupSerializer,
)
from .services import (
    add_book_to_group,
    add_user_to_group,
    delete_library_group,
    remove_book_from_group,
    remove_user_from_group,
    update_user_group_membership,
)
from ..models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from .public_group import get_public_group, is_public_group
from ..view_mixins import ClientBearerReadOnlyMixin


def _attach_group_preview_books(*, groups, user) -> None:
    group_list = list(groups)
    group_ids = [group.id for group in group_list]
    if not group_ids:
        return

    queryset = BookGroupAssignment.objects.select_related("book").filter(group_id__in=group_ids)
    if not policies.can_manage_library(user):
        visible_assignment = BookGroupAssignment.objects.filter(
            book_id=OuterRef("book_id"),
            group__memberships__user=user,
        )
        queryset = queryset.filter(Exists(visible_assignment))

    queryset = (
        queryset.annotate(
            _preview_parent_id=F("group_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("group_id")],
                order_by=[
                    Random(),
                    F("book_id").asc(),
                ],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("_preview_parent_id", "_preview_rank")
    )

    attach_preview_books_from_queryset(
        parents=group_list,
        queryset=queryset,
        get_book=lambda assignment: assignment.book,
    )


def _membership_payload(membership: LibraryGroupMembership) -> dict[str, Any]:
    user = membership.user
    profile = get_or_create_profile(user=user)
    return {
        "id": membership.id,
        "user": {
            "profile_id": profile.id,
            "username": user.get_username(),
            "email": user.email or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
        },
        "is_curator": bool(membership.is_curator),
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def _advanced_groups_disabled_response() -> Response:
    return api_error_response(
        code=ErrorCode.ADVANCED_GROUPS_DISABLED,
        message="Advanced library groups are disabled.",
        detail=(
            "Enable advanced library groups in Server Settings before changing "
            "non-Public groups, memberships, curators, or assignments."
        ),
        hint=(
            "Public Library/Common Room settings and Public book assignments "
            "remain available."
        ),
        status_code=status.HTTP_403_FORBIDDEN,
    )


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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        groups = list(page) if page is not None else list(queryset)

        if include_preview_books(request):
            _attach_group_preview_books(groups=groups, user=request.user)

        serializer = self.get_serializer(groups, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if include_preview_books(request):
            _attach_group_preview_books(groups=[instance], user=request.user)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for presentation fields.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        if not server_settings.advanced_library_groups_enabled():
            return _advanced_groups_disabled_response()

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
        if not server_settings.advanced_library_groups_enabled():
            return _advanced_groups_disabled_response()

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = LibraryGroupSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()
        if not is_public_group(group) and not server_settings.advanced_library_groups_enabled():
            return _advanced_groups_disabled_response()

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

        if (
            not is_public_group(group)
            and not server_settings.advanced_library_groups_enabled()
        ):
            return _advanced_groups_disabled_response()

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

        if (
            not is_public_group(group)
            and not server_settings.advanced_library_groups_enabled()
        ):
            return _advanced_groups_disabled_response()

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
            payload = [_membership_payload(membership) for membership in memberships]
            serializer = LibraryGroupMembershipSerializer(payload, many=True)
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        if not server_settings.advanced_library_groups_enabled():
            return _advanced_groups_disabled_response()

        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")

        create = LibraryGroupMembershipCreateSerializer(data=request.data or {})
        create.is_valid(raise_exception=True)
        data = create.validated_data

        profile_id = data.get("profile_id")
        is_curator = bool(data.get("is_curator", False))
        try:
            profile = UserProfile.objects.select_related("user").get(pk=profile_id)
            target = profile.user
        except (UserProfile.DoesNotExist, ValidationError, ValueError):
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="User not found.",
                detail=f"No user profile with profile_id={profile_id}.",
                hint="Use a valid profile_id from /api/v1/accounts/users/.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = add_user_to_group(
                actor=request.user,
                target_user=target,
                group=group,
                is_curator=is_curator,
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership request.",
                detail=str(exc),
                hint="Use is_curator=true only for non-Public groups.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = _membership_payload(membership)
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
        if not server_settings.advanced_library_groups_enabled():
            return _advanced_groups_disabled_response()

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
                actor=request.user,
                membership=membership,
                is_curator=bool(data["is_curator"]),
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership update.",
                detail=str(exc),
                hint="Use is_curator=true only for non-Public groups.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = _membership_payload(membership)
        serializer = LibraryGroupMembershipSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
