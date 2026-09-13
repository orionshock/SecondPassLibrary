from __future__ import annotations

from typing import Any, cast

from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.roles import is_owner
from accounts.client_sessions.authentication import ClientBearerAuthentication
from core import server_settings
from core.server_configuration import (
    ServerConfigurationPatchError,
    get_owner_server_configuration,
    update_owner_server_configuration,
)
from core.server_info import server_info_payload


class ServerInfoView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]

    def get(self, request):
        return Response(server_info_payload(), status=status.HTTP_200_OK)


class ServerSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_owner(self, request) -> None:
        if not is_owner(getattr(request, "user", None)):
            raise PermissionDenied("Not allowed.")

    def get(self, request):
        self._require_owner(request)
        return Response(get_owner_server_configuration(), status=status.HTTP_200_OK)

    def patch(self, request):
        self._require_owner(request)
        data = cast(dict[str, Any], request.data or {})

        try:
            payload = update_owner_server_configuration(patch=data, actor=request.user)
        except ServerConfigurationPatchError as exc:
            if exc.unknown_fields:
                raise ValidationError(
                    detail={
                        "detail": "Unknown fields.",
                        "fields": list(exc.unknown_fields),
                    }
                ) from exc
            raise ValidationError(detail=exc.errors) from exc
        return Response(payload, status=status.HTTP_200_OK)


class AdvancedLibraryGroupsEnableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_owner(getattr(request, "user", None)):
            raise PermissionDenied("Not allowed.")

        server_settings.enable_advanced_library_groups()
        return Response(get_owner_server_configuration(), status=status.HTTP_200_OK)
