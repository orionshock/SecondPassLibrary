from __future__ import annotations

from typing import Any, cast

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from core import policies
from core import server_settings


class ServerSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_owner(self, request) -> None:
        if not policies.is_owner(getattr(request, "user", None)):
            raise PermissionDenied("Not allowed.")

    def get(self, request):
        self._require_owner(request)
        return Response(
            {
                "server_name": server_settings.get_server_name(),
                "server_description": server_settings.get_server_description(),
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        self._require_owner(request)
        data = cast(dict[str, Any], request.data or {})

        allowed_keys = {"server_name", "server_description"}
        unknown = sorted(set(data.keys()) - allowed_keys)
        if unknown:
            raise ValidationError(detail={"detail": "Unknown fields.", "fields": unknown})

        errors: dict[str, list[str]] = {}

        if "server_name" in data:
            try:
                server_settings.set_server_name(str(data.get("server_name") or ""))
            except ValueError as exc:
                errors.setdefault("server_name", []).append(str(exc))

        if "server_description" in data:
            try:
                server_settings.set_server_description(
                    str(data.get("server_description") or "")
                )
            except ValueError as exc:
                errors.setdefault("server_description", []).append(str(exc))

        if errors:
            raise ValidationError(detail=errors)

        return Response(
            {
                "server_name": server_settings.get_server_name(),
                "server_description": server_settings.get_server_description(),
            },
            status=status.HTTP_200_OK,
        )
