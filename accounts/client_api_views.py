from __future__ import annotations

from typing import Any, cast

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from . import client_api
from .models import ClientLoginRequest


class ClientApiDiscoveryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        base = request.build_absolute_uri("/")
        payload = {
            "discovery_version": "0.1",
            "api_base_url": request.build_absolute_uri("/api/v1/"),
            "login_request_endpoint": request.build_absolute_uri(
                "/api/v1/client-api/login-requests/"
            ),
            "authorize_url": request.build_absolute_uri("/client-api/authorize/"),
            "poll_endpoint_template": request.build_absolute_uri(
                "/api/v1/client-api/login-requests/{id}/poll/"
            ),
            "token_type": "Bearer",
            "server_base_url": base,
        }
        return Response(payload, status=status.HTTP_200_OK)


class ClientLoginRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = cast(dict[str, Any], request.data or {})
        client_name = str(data.get("client_name") or "").strip()
        client_type = str(data.get("client_type") or "").strip()

        ua = (request.META.get("HTTP_USER_AGENT") or "")[:4000]
        ip = request.META.get("REMOTE_ADDR") or None

        try:
            obj, code = client_api.create_login_request(
                client_name=client_name,
                client_type=client_type,
                request_user_agent=ua,
                request_ip=ip,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        authorize_url = request.build_absolute_uri(
            f"/client-api/authorize/?code={code}"
        )
        poll_url = request.build_absolute_uri(
            f"/api/v1/client-api/login-requests/{obj.pk}/poll/"
        )

        return Response(
            {
                "id": str(obj.pk),
                "code": code,
                "authorize_url": authorize_url,
                "poll_url": poll_url,
                "expires_at": obj.expires_at.isoformat(),
                "interval": client_api.POLL_INTERVAL_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )


class ClientLoginRequestPollView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, login_request_id: str):
        try:
            obj = ClientLoginRequest.objects.get(pk=login_request_id)
        except ClientLoginRequest.DoesNotExist:
            return Response({"status": "expired"}, status=status.HTTP_200_OK)

        now = timezone.now()
        if client_api.is_login_request_expired(obj, now=now):
            if obj.status not in (
                ClientLoginRequest.STATUS_CONSUMED,
                ClientLoginRequest.STATUS_DENIED,
                ClientLoginRequest.STATUS_EXPIRED,
            ):
                obj.status = ClientLoginRequest.STATUS_EXPIRED
                obj.save(update_fields=["status", "updated_at"])
            return Response({"status": "expired"}, status=status.HTTP_200_OK)

        if obj.status == ClientLoginRequest.STATUS_PENDING:
            return Response({"status": "pending"}, status=status.HTTP_200_OK)
        if obj.status == ClientLoginRequest.STATUS_DENIED:
            return Response({"status": "denied"}, status=status.HTTP_200_OK)
        if obj.status == ClientLoginRequest.STATUS_CONSUMED:
            return Response({"status": "consumed"}, status=status.HTTP_200_OK)

        if obj.status == ClientLoginRequest.STATUS_APPROVED:
            result = client_api.consume_login_request(login_request=obj)
            if result is None:
                # Another poll likely consumed it already, or the request is no longer
                # eligible to consume. Never return `approved` without a token.
                obj.refresh_from_db(fields=["status", "expires_at"])
                if obj.status == ClientLoginRequest.STATUS_CONSUMED:
                    return Response({"status": "consumed"}, status=status.HTTP_200_OK)
                if client_api.is_login_request_expired(obj, now=now):
                    return Response({"status": "expired"}, status=status.HTTP_200_OK)
                if obj.status == ClientLoginRequest.STATUS_APPROVED:
                    # Contract-safe fallback: if we cannot return a token, treat as consumed.
                    return Response({"status": "consumed"}, status=status.HTTP_200_OK)
                return Response({"status": str(obj.status)}, status=status.HTTP_200_OK)

            return Response(
                {
                    "status": "approved",
                    "access_token": result.access_token,
                    "token_type": "Bearer",
                    "client_session": {
                        "id": str(result.session.pk),
                        "name": result.session.name,
                        "client_type": result.session.client_type,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Safety fallback
        return Response({"status": str(obj.status)}, status=status.HTTP_200_OK)
