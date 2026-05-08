from django.contrib.auth import get_user_model
from typing import cast
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from .models import UserProfile
from .serializers import (
    CurrentUserSerializer,
    ManagedUserPatchSerializer,
    ManagedUserSerializer,
    UserProfileSerializer,
)
from .services import (
    build_current_user_me_payload,
    get_or_create_profile,
    update_user_via_management_api,
)
from core import policies


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


class ManagedUserViewSet(
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

        qs = User.objects.all().order_by("username")
        if policies.is_owner(user):
            return qs

        # Managers should not see Owner accounts via normal product APIs.
        return qs.filter(is_superuser=False)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        users = list(page) if page is not None else list(queryset)
        payload = []
        for user in users:
            profile = get_or_create_profile(user=user)
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
                }
            )
        serializer = ManagedUserSerializer(payload, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        profile = get_or_create_profile(user=user)
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
        }
        serializer = ManagedUserSerializer(payload)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        target = self.get_object()

        patch = ManagedUserPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = patch.validated_data

        update_user_via_management_api(
            actor=request.user,
            target_user=target,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            is_active=data.get("is_active"),
            role=data.get("role"),
        )

        profile = get_or_create_profile(user=target)
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
        }
        serializer = ManagedUserSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
