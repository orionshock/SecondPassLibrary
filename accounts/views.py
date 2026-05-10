from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from typing import Any, cast
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from .models import UserProfile
from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    CurrentUserPatchSerializer,
    ManagedUserPatchSerializer,
    ManagedUserCreateSerializer,
    ManagedUserSerializer,
    UserProfileSerializer,
)
from .services import (
    build_current_user_me_payload,
    change_current_user_password,
    create_managed_user,
    get_or_create_profile,
    reset_managed_user_password,
    update_current_user_via_me_api,
    update_user_via_management_api,
)
from core import policies
from library.models import LibraryGroupMembership, is_public_group


User = get_user_model()


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Explicit ordering avoids DRF's UnorderedObjectListWarning under pagination.
        return (
            UserProfile.objects.select_related("user")
            .filter(user=self.request.user)
            .order_by("user__username", "id")
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = build_current_user_me_payload(user=request.user)
        serializer = CurrentUserSerializer(payload)
        return Response(serializer.data)

    def patch(self, request):
        patch = CurrentUserPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = cast(dict[str, Any], patch.validated_data)

        update_current_user_via_me_api(
            user=request.user,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )

        payload = build_current_user_me_payload(user=request.user)
        serializer = CurrentUserSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CurrentUserChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = ChangePasswordSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        data = cast(dict[str, Any], body.validated_data)

        try:
            change_current_user_password(
                user=request.user,
                current_password=str(data.get("current_password") or ""),
                new_password=str(data.get("new_password") or ""),
                confirm_password=str(data.get("confirm_password") or ""),
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or {"detail": exc.messages}
            raise DRFValidationError(detail=detail) from exc
        update_session_auth_hash(request, request.user)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


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
        if not policies.can_manage_users(user):
            raise PermissionDenied("Not allowed.")

        qs = User.objects.all().order_by("username").prefetch_related(
            "library_group_memberships__group"
        )
        if policies.is_owner(user):
            return qs

        # Managers should not see Owner accounts via normal product APIs.
        return qs.filter(is_superuser=False)

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

        user = result.user
        profile = get_or_create_profile(user=user)
        memberships = list(
            getattr(user, "library_group_memberships", LibraryGroupMembership.objects.none())
            .all()
        )
        groups = []
        for membership in memberships:
            group = membership.group
            groups.append(
                {
                    "membership_id": membership.id,
                    "id": group.id,
                    "name": group.name,
                    "slug": group.slug,
                    "membership_role": membership.role,
                    "is_public_group": is_public_group(group),
                }
            )
        user_payload = {
            "id": cast(int, user.pk),
            "username": user.get_username(),
            "email": user.email or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_active": bool(getattr(user, "is_active", True)),
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "is_owner": policies.is_owner(user),
            "profile_id": profile.id,
            "role": profile.role,
            "must_change_password": bool(profile.must_change_password),
            "groups": sorted(groups, key=lambda g: (g["name"], g["slug"])),
        }

        serializer = ManagedUserSerializer(user_payload)
        return Response(
            {
                "user": serializer.data,
                "temporary_password": result.temporary_password,
                "message": "Show this password now. It will not be shown again.",
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        users = list(page) if page is not None else list(queryset)
        payload = []
        for user in users:
            profile = get_or_create_profile(user=user)
            memberships = list(
                getattr(user, "library_group_memberships", LibraryGroupMembership.objects.none())
                .all()
            )
            groups = []
            for membership in memberships:
                group = membership.group
                groups.append(
                    {
                        "membership_id": membership.id,
                        "id": group.id,
                        "name": group.name,
                        "slug": group.slug,
                        "membership_role": membership.role,
                        "is_public_group": is_public_group(group),
                    }
                )
            payload.append(
                {
                    "id": cast(int, user.pk),
                    "username": user.get_username(),
                    "email": user.email or "",
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "is_active": bool(getattr(user, "is_active", True)),
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                    "is_owner": policies.is_owner(user),
                    "profile_id": profile.id,
                    "role": profile.role,
                    "must_change_password": bool(profile.must_change_password),
                    "groups": sorted(groups, key=lambda g: (g["name"], g["slug"])),
                }
            )
        serializer = ManagedUserSerializer(payload, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        profile = get_or_create_profile(user=user)
        memberships = list(
            getattr(user, "library_group_memberships", LibraryGroupMembership.objects.none())
            .all()
        )
        groups = []
        for membership in memberships:
            group = membership.group
            groups.append(
                {
                    "membership_id": membership.id,
                    "id": group.id,
                    "name": group.name,
                    "slug": group.slug,
                    "membership_role": membership.role,
                    "is_public_group": is_public_group(group),
                }
            )
        payload = {
            "id": cast(int, user.pk),
            "username": user.get_username(),
            "email": user.email or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_active": bool(getattr(user, "is_active", True)),
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "is_owner": policies.is_owner(user),
            "profile_id": profile.id,
            "role": profile.role,
            "must_change_password": bool(profile.must_change_password),
            "groups": sorted(groups, key=lambda g: (g["name"], g["slug"])),
        }
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

        profile = get_or_create_profile(user=target)
        memberships = list(
            getattr(target, "library_group_memberships", LibraryGroupMembership.objects.none())
            .all()
        )
        groups = []
        for membership in memberships:
            group = membership.group
            groups.append(
                {
                    "membership_id": membership.id,
                    "id": group.id,
                    "name": group.name,
                    "slug": group.slug,
                    "membership_role": membership.role,
                    "is_public_group": is_public_group(group),
                }
            )
        payload = {
            "id": cast(int, target.pk),
            "username": target.get_username(),
            "email": target.email or "",
            "first_name": target.first_name or "",
            "last_name": target.last_name or "",
            "is_active": bool(getattr(target, "is_active", True)),
            "date_joined": target.date_joined,
            "last_login": target.last_login,
            "is_owner": policies.is_owner(target),
            "profile_id": profile.id,
            "role": profile.role,
            "must_change_password": bool(profile.must_change_password),
            "groups": sorted(groups, key=lambda g: (g["name"], g["slug"])),
        }
        serializer = ManagedUserSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ManagedUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id: str):
        if not user_id:
            raise PermissionDenied("Not allowed.")

        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist as exc:
            raise PermissionDenied("Not allowed.") from exc

        try:
            result = reset_managed_user_password(
                actor=request.user, target_user=target_user
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or {"detail": exc.messages}
            raise DRFValidationError(detail=detail) from exc
        return Response(
            {
                "username": result.username,
                "temporary_password": result.temporary_password,
                "copy_block": result.copy_block,
                "message": "Show this password now. It will not be shown again.",
            },
            status=status.HTTP_200_OK,
        )
