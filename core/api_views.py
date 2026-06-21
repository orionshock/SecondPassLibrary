from __future__ import annotations

from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from core import policies
from core import server_settings
from library.group_services import configure_public_group, get_public_group


def _server_settings_payload() -> dict[str, Any]:
    public_group = get_public_group()
    return {
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
        "public_group_name": public_group.name,
        "public_group_description": public_group.description,
        "advanced_library_groups_enabled": (
            server_settings.get_advanced_library_groups_enabled()
        ),
    }


class ServerSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_owner(self, request) -> None:
        if not policies.is_owner(getattr(request, "user", None)):
            raise PermissionDenied("Not allowed.")

    def get(self, request):
        self._require_owner(request)
        return Response(_server_settings_payload(), status=status.HTTP_200_OK)

    def patch(self, request):
        self._require_owner(request)
        data = cast(dict[str, Any], request.data or {})

        allowed_keys = {
            "server_name",
            "server_description",
            "public_group_name",
            "public_group_description",
            "advanced_library_groups_enabled",
        }
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

        public_name = data.get("public_group_name", None)
        public_description = data.get("public_group_description", None)
        if public_name is not None or public_description is not None:
            current_public = get_public_group()
            try:
                configure_public_group(
                    name=(
                        str(public_name)
                        if public_name is not None
                        else current_public.name
                    ),
                    description=(
                        str(public_description or "")
                        if public_description is not None
                        else current_public.description
                    ),
                )
            except DjangoValidationError as exc:
                for field, messages in exc.message_dict.items():
                    errors.setdefault(field, []).extend(messages)

        if "advanced_library_groups_enabled" in data:
            value = data["advanced_library_groups_enabled"]
            if not isinstance(value, bool):
                errors.setdefault("advanced_library_groups_enabled", []).append(
                    "Must be true or false."
                )
            else:
                server_settings.set_advanced_library_groups_enabled(value)

        if errors:
            raise ValidationError(detail=errors)

        return Response(_server_settings_payload(), status=status.HTTP_200_OK)
