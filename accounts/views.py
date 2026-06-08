from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from typing import Any, cast
from rest_framework import mixins, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import UserProfile
from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    CurrentUserPatchSerializer,
    CurrentUserClientSessionSerializer,
    ManagedUserPatchSerializer,
    ManagedUserCreateSerializer,
    ManagedUserSerializer,
    UserProfileSerializer,
)
from .services import (
    build_current_user_me_payload,
    change_current_user_password,
    create_managed_user,
    reset_managed_user_password,
    update_current_user_via_me_api,
    update_user_via_management_api,
)
from .user_payloads import managed_user_create_envelope, managed_user_payload
from core import policies
from accounts import session_control
from accounts.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession


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
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]

    def get(self, request):
        payload = build_current_user_me_payload(user=request.user)
        serializer = CurrentUserSerializer(payload)
        return Response(serializer.data)

    def patch(self, request):
        # Phase 1 guardrail: Client API bearer tokens may read /me but not update it.
        if isinstance(getattr(request, "auth", None), UserClientSession):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

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
        session_control.user_changed_own_password(
            request.user, getattr(getattr(request, "session", None), "session_key", None)
        )
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class CurrentUserLogoutOtherWebSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_session_key = getattr(getattr(request, "session", None), "session_key", None)
        session_control.revoke_other_web_sessions(request.user, current_session_key)
        return Response({"message": "Other web sessions logged out."}, status=status.HTTP_200_OK)


class CurrentUserClientSessionsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]

    def get(self, request):
        qs = (
            UserClientSession.objects.filter(user=request.user, revoked_at__isnull=True)
            .order_by("-created_at", "id")
        )
        return Response(CurrentUserClientSessionSerializer(qs, many=True).data)


class CurrentUserClientSessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]

    def delete(self, request, session_id: str):
        # Anti-leakage: only operate on the current user's sessions.
        obj = get_object_or_404(
            UserClientSession, pk=session_id, user=request.user, revoked_at__isnull=True
        )
        now = timezone.now()
        UserClientSession.objects.filter(pk=obj.pk).update(revoked_at=now, updated_at=now)
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        envelope = managed_user_create_envelope(result)
        serializer = ManagedUserSerializer(envelope["user"])
        envelope["user"] = serializer.data
        return Response(envelope, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
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
        session_control.admin_reset_user_password(target_user)
        return Response(
            {
                "username": result.username,
                "temporary_password": result.temporary_password,
                "copy_block": result.copy_block,
                "message": "Show this password now. It will not be shown again.",
            },
            status=status.HTTP_200_OK,
        )
