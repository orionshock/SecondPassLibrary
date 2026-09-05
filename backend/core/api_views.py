from __future__ import annotations

from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.roles import is_owner
from accounts.client_sessions.authentication import ClientBearerAuthentication
from core import server_settings
from core.server_info import server_info_payload
from library.groups.public_services import configure_public_group
from library.groups.public_group import get_public_group


def _server_settings_payload() -> dict[str, Any]:
    public_group = get_public_group()
    return {
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
        "server_banner_message": server_settings.get_server_banner_message(),
        "public_group_name": public_group.name,
        "public_group_description": public_group.description,
        "advanced_library_groups_enabled": (
            server_settings.get_advanced_library_groups_enabled()
        ),
        "second_pass_reader_web_client_url": (
            server_settings.get_second_pass_reader_web_client_url()
        ),
        "second_pass_reader_web_client_url_locked": (
            server_settings.second_pass_reader_web_client_url_locked()
        ),
    }


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
        return Response(_server_settings_payload(), status=status.HTTP_200_OK)

    def patch(self, request):
        self._require_owner(request)
        data = cast(dict[str, Any], request.data or {})

        allowed_keys = {
            "server_name",
            "server_description",
            "server_banner_message",
            "second_pass_reader_web_client_url",
            "public_group_name",
            "public_group_description",
        }
        unknown = sorted(set(data.keys()) - allowed_keys)
        if unknown:
            raise ValidationError(detail={"detail": "Unknown fields.", "fields": unknown})

        errors: dict[str, list[str]] = {}

        identity_keys = {
            "server_name",
            "server_description",
            "server_banner_message",
        }
        if identity_keys.intersection(data):
            try:
                server_settings.set_server_identity(
                    name=(
                        str(data.get("server_name") or "")
                        if "server_name" in data
                        else server_settings.get_server_name()
                    ),
                    description=(
                        str(data.get("server_description") or "")
                        if "server_description" in data
                        else server_settings.get_server_description()
                    ),
                    banner_message=(
                        str(data.get("server_banner_message") or "")
                        if "server_banner_message" in data
                        else server_settings.get_server_banner_message()
                    ),
                )
            except DjangoValidationError as exc:
                for field, messages in exc.message_dict.items():
                    errors.setdefault(field, []).extend(messages)

        if "second_pass_reader_web_client_url" in data:
            try:
                server_settings.set_second_pass_reader_web_client_url(
                    str(data.get("second_pass_reader_web_client_url") or "")
                )
            except ValueError as exc:
                errors.setdefault("second_pass_reader_web_client_url", []).append(
                    str(exc)
                )

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
                    wire_field = (
                        "public_group_description"
                        if field == "description"
                        else field
                    )
                    errors.setdefault(wire_field, []).extend(messages)

        if errors:
            raise ValidationError(detail=errors)

        return Response(_server_settings_payload(), status=status.HTTP_200_OK)


class AdvancedLibraryGroupsEnableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_owner(getattr(request, "user", None)):
            raise PermissionDenied("Not allowed.")

        server_settings.enable_advanced_library_groups()
        return Response(_server_settings_payload(), status=status.HTTP_200_OK)
