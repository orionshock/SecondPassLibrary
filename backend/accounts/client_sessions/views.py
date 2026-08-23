from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlencode

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from accounts.request_identity import canonical_client_ip
from accounts import session_control
from accounts.models import ClientLoginRequest, UserClientSession
from core import server_settings

from . import services
from .authentication import ClientBearerAuthentication
from .serializers import CurrentUserClientSessionSerializer


PAIRING_CACHE_CONTROL = "no-store, private"
PAIRING_PRAGMA = "no-cache"


class CurrentUserClientSessionsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]

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
        ClientBearerAuthentication,
    ]

    def delete(self, request, session_id: str):
        obj = _client_session_revoke_target(request=request, session_id=session_id)
        session_control.revoke_client_session(obj, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _client_session_revoke_target(*, request, session_id: str) -> UserClientSession:
    authenticator = request.successful_authenticator
    if isinstance(authenticator, ClientBearerAuthentication):
        authenticated_session = request.auth
        if not isinstance(authenticated_session, UserClientSession):
            raise Http404
        queryset = UserClientSession.objects.filter(
            pk=authenticated_session.pk,
            revoked_at__isnull=True,
        )
        return get_object_or_404(queryset, pk=session_id)

    if isinstance(authenticator, SessionAuthentication):
        return get_object_or_404(
            UserClientSession,
            pk=session_id,
            user=request.user,
            revoked_at__isnull=True,
        )

    raise Http404


class PairingNoStoreMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = PAIRING_CACHE_CONTROL
        response["Pragma"] = PAIRING_PRAGMA
        return response


class ClientApiDiscoveryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        base = request.build_absolute_uri("/")
        payload = {
            "discovery_version": "0.1",
            "server_name": server_settings.get_server_name(),
            "server_description": server_settings.get_server_description(),
            "api_base_url": request.build_absolute_uri("/api/v1/"),
            "login_request_endpoint": request.build_absolute_uri(
                "/api/v1/client-api/login-requests/"
            ),
            "poll_endpoint_template": request.build_absolute_uri(
                "/api/v1/client-api/login-requests/{id}/poll/"
            ),
            "consume_endpoint_template": request.build_absolute_uri(
                "/api/v1/client-api/login-requests/{id}/poll/"
            ),
            "token_type": "Bearer",
            "server_base_url": base,
        }
        return Response(payload, status=status.HTTP_200_OK)


class ClientLoginRequestCreateView(PairingNoStoreMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = cast(dict[str, Any], request.data or {})
        client_name = str(data.get("client_name") or "").strip()
        client_type = str(data.get("client_type") or "").strip()

        ua = request.META.get("HTTP_USER_AGENT") or ""
        ip = canonical_client_ip(request)

        try:
            obj, code = services.create_login_request(
                client_name=client_name,
                client_type=client_type,
                request_user_agent=ua,
                request_ip=ip,
            )
        except services.PairingRequestThrottled:
            return Response(
                {"detail": "Pairing request limit reached. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        poll_url = request.build_absolute_uri(
            f"/api/v1/client-api/login-requests/{obj.pk}/poll/"
        )
        authorize_url = request.build_absolute_uri(
            f"/profile/client-pairing?{urlencode({'code': code})}"
        )

        return Response(
            {
                "id": str(obj.pk),
                "code": code,
                "authorize_url": authorize_url,
                "poll_url": poll_url,
                "consume_url": poll_url,
                "expires_at": obj.expires_at.isoformat(),
                "interval": services.POLL_INTERVAL_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )


class ClientLoginRequestPollView(PairingNoStoreMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request, login_request_id: str):
        obj = _get_login_request(login_request_id)
        return Response(
            {"status": _login_request_state(obj)},
            status=status.HTTP_200_OK,
        )

    def post(self, request, login_request_id: str):
        obj = _get_login_request(login_request_id)
        state = _login_request_state(obj)
        if obj is None or state != ClientLoginRequest.STATUS_APPROVED:
            if obj is not None and state in (
                ClientLoginRequest.STATUS_CONSUMED,
                ClientLoginRequest.STATUS_EXPIRED,
            ):
                services.log_consumption_rejection(
                    login_request=obj,
                    state=state,
                )
            return Response({"status": state}, status=status.HTTP_200_OK)

        result = services.consume_login_request(login_request=obj)
        if result is None:
            obj.refresh_from_db(fields=["status", "expires_at"])
            return Response(
                {"status": _login_request_state(obj)},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "status": ClientLoginRequest.STATUS_CONSUMED,
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


class ClientPairingLookupView(PairingNoStoreMixin, APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = str((request.data or {}).get("code") or "").strip()
        login_request = services.get_pending_login_request_for_code(code)
        if login_request is None:
            return Response(
                {"detail": "Invalid or expired pairing code."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "code": services.format_human_code(code),
                "client_name": login_request.client_name,
                "client_type": login_request.client_type,
                "expires_at": login_request.expires_at.isoformat(),
            }
        )


class ClientPairingDecisionView(PairingNoStoreMixin, APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = cast(dict[str, Any], request.data or {})
        code = str(data.get("code") or "").strip()
        action = str(data.get("action") or "").strip().lower()
        login_request = services.get_pending_login_request_for_code(code)
        if login_request is None:
            return Response(
                {"detail": "Invalid or expired pairing code."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            if action == "approve":
                client_name = str(data.get("client_name") or "").strip()
                if not client_name:
                    raise ValueError("Device/client name is required.")
                if len(client_name) > 200:
                    raise ValueError("Device/client name is too long.")
                services.approve_login_request(
                    login_request=login_request,
                    user=request.user,
                    client_name=client_name,
                )
            elif action == "deny":
                services.deny_login_request(login_request=login_request, user=request.user)
            else:
                raise ValueError("Action must be approve or deny.")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "approved" if action == "approve" else "denied"})


def _get_login_request(login_request_id: str) -> ClientLoginRequest | None:
    try:
        return ClientLoginRequest.objects.get(pk=login_request_id)
    except (ClientLoginRequest.DoesNotExist, DjangoValidationError, ValueError):
        return None


def _login_request_state(login_request: ClientLoginRequest | None) -> str:
    if login_request is None:
        return ClientLoginRequest.STATUS_EXPIRED
    if login_request.status in (
        ClientLoginRequest.STATUS_DENIED,
        ClientLoginRequest.STATUS_CONSUMED,
        ClientLoginRequest.STATUS_EXPIRED,
    ):
        return login_request.status
    if services.is_login_request_expired(login_request, now=timezone.now()):
        return ClientLoginRequest.STATUS_EXPIRED
    return login_request.status
