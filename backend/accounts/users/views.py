from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import generics, mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.roles import is_manager, is_owner
from core.server_settings import advanced_library_groups_enabled

from .payloads import managed_user_create_envelope, managed_user_payload
from .queries import filter_and_order_managed_users
from .serializers import (
    ManagedUserCreateSerializer,
    ManagedUserListQuerySerializer,
    ManagedUserPatchSerializer,
    ManagedUserSerializer,
    UserChoiceQuerySerializer,
    UserChoiceSerializer,
)
from .services import create_managed_user, update_user_via_management_api


User = get_user_model()


class ManagedUserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not is_manager(user):
            raise PermissionDenied("Not allowed.")

        qs = (
            User.objects.select_related("profile")
            .all()
            .order_by("username")
            .prefetch_related("library_group_memberships__group")
        )
        if is_owner(user):
            return qs

        # Managers should not see Owner accounts via normal product APIs.
        return qs.filter(is_superuser=False)

    def get_object(self):
        profile_id = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        if not profile_id:
            raise Http404()
        try:
            obj = self.filter_queryset(self.get_queryset()).get(profile__id=profile_id)
        except (User.DoesNotExist, DjangoValidationError, ValueError) as exc:
            raise Http404() from exc
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        create = ManagedUserCreateSerializer(data=request.data or {})
        create.is_valid(raise_exception=True)
        data = cast(dict[str, Any], create.validated_data)

        result = create_managed_user(
            actor=request.user,
            username=data["username"],
            email=data.get("email") or "",
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            role=data.get("role") or UserProfile.ROLE_READER,
            is_active=bool(data.get("is_active", True)),
        )

        envelope = managed_user_create_envelope(result)
        serializer = ManagedUserSerializer(envelope["user"])
        envelope["user"] = serializer.data
        return Response(envelope, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        query = ManagedUserListQuerySerializer(
            data=request.query_params,
            context={"advanced_groups_enabled": advanced_library_groups_enabled()},
        )
        query.is_valid(raise_exception=True)
        queryset = filter_and_order_managed_users(
            self.get_queryset(), query=cast(dict[str, Any], query.validated_data)
        )
        page = self.paginate_queryset(queryset)
        users = list(page) if page is not None else list(queryset)
        payload = [managed_user_payload(user) for user in users]
        serializer = ManagedUserSerializer(payload, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        payload = managed_user_payload(user)
        serializer = ManagedUserSerializer(payload)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        target = self.get_object()

        patch = ManagedUserPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = cast(dict[str, Any], patch.validated_data)

        update_user_via_management_api(
            actor=request.user,
            target_user=target,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            is_active=data.get("is_active"),
            role=data.get("role"),
            must_change_password=data.get("must_change_password"),
        )

        payload = managed_user_payload(target)
        serializer = ManagedUserSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserChoiceListView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserChoiceSerializer

    def get_queryset(self):
        if not is_manager(self.request.user):
            raise PermissionDenied("Not allowed.")

        query = UserChoiceQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        data = cast(dict[str, Any], query.validated_data)

        users = User.objects.select_related("profile").filter(is_active=True)
        if not is_owner(self.request.user):
            users = users.filter(is_superuser=False)

        search = str(data.get("q") or "").strip()
        if search:
            users = users.filter(username__icontains=search)

        exclude_group = data.get("exclude_group")
        if exclude_group:
            users = users.exclude(
                library_group_memberships__group_id=exclude_group
            )

        return users.order_by("username", "id")

