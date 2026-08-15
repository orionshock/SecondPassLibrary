from typing import Any, cast

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChangePasswordSerializer
from .services import change_current_user_password, reset_managed_user_password


User = get_user_model()


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
                current_session_key=getattr(
                    getattr(request, "session", None), "session_key", None
                ),
            )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or {"detail": exc.messages}
            raise DRFValidationError(detail=detail) from exc
        update_session_auth_hash(request, request.user)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

class ManagedUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, profile_id: str):
        if not profile_id:
            raise PermissionDenied("Not allowed.")

        try:
            target_user = User.objects.select_related("profile").get(profile__id=profile_id)
        except (User.DoesNotExist, DjangoValidationError, ValueError) as exc:
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

