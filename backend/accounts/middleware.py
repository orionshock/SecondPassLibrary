from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from accounts.browser_account_facts import get_browser_account_facts
from accounts.operational_logging import logger, user_uuid
from accounts.request_identity import get_client_ip
from accounts.session_control import WEB_SESSION_GENERATION_KEY
from library.cover_objects import is_immutable_public_cover_path

from .models import UserWebSession


PASSWORD_CHANGE_REQUIRED_CODE = "password_change_required"
PASSWORD_CHANGE_REQUIRED_DETAIL = "Password change required."
PASSWORD_POLICY_CHECK_FAILED_CODE = "password_policy_check_failed"
PASSWORD_POLICY_CHECK_FAILED_DETAIL = "Unable to verify password-change policy."

_ALLOWED_API_READS = {
    "/api/v1/accounts/me/",
    "/api/v1/server/info/",
}
_ALLOWED_API_PATHS = {
    "/api/v1/accounts/me/change-password/",
    "/api/v1/health/",
}
_ALLOWED_BROWSER_PATHS = {
    "/",
    "/favicon.ico",
    "/login/",
    "/logout/",
    "/setup/",
    "/.well-known/secondpass",
}


class WebSessionGenerationMiddleware:
    """Invalidate browser sessions superseded by an account-wide revocation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_immutable_public_cover_path(request.path_info):
            return self.get_response(request)
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        if user and not getattr(user, "is_anonymous", True) and session is not None:
            try:
                facts = get_browser_account_facts(request)
                if facts is None:
                    raise RuntimeError("Authenticated browser account facts unavailable.")
            except Exception:
                if _is_api_path(request.path_info):
                    return JsonResponse(
                        {"detail": "Unable to verify browser session."}, status=503
                    )
                return redirect("/login/")

            stored_generation = session.get(WEB_SESSION_GENERATION_KEY, 0)
            if stored_generation != facts.web_session_generation:
                logout(request)
            elif WEB_SESSION_GENERATION_KEY not in session:
                session[WEB_SESSION_GENERATION_KEY] = facts.web_session_generation

        return self.get_response(request)


_ALLOWED_BROWSER_PREFIXES = (
    "/dashboard",
    "/groups",
    "/imports",
    "/library",
    "/marginalia",
    "/profile",
    "/server",
    "/settings",
    "/shelves",
    "/static/",
    "/users",
)


class MustChangePasswordMiddleware:
    """Restrict flagged Django sessions without changing bearer authentication."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_immutable_public_cover_path(request.path_info):
            return self.get_response(request)
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        path_info = request.path_info
        try:
            facts = get_browser_account_facts(request)
            if facts is None:
                raise RuntimeError("Authenticated browser account facts unavailable.")
            required = facts.must_change_password
        except Exception as exc:
            logger.error(
                "Password-change enforcement failed: exception=%s",
                type(exc).__name__,
            )
            if _is_api_path(path_info):
                return JsonResponse(
                    {
                        "detail": PASSWORD_POLICY_CHECK_FAILED_DETAIL,
                        "code": PASSWORD_POLICY_CHECK_FAILED_CODE,
                    },
                    status=500,
                )
            raise

        if not required or _password_change_path_allowed(path_info, request.method):
            return self.get_response(request)

        if _is_api_path(path_info):
            area = _bounded_api_area(path_info)
            logger.debug(
                "Password-change-required API request blocked: actor=%s method=%s area=%s",
                user_uuid(user),
                request.method,
                area,
            )
            return JsonResponse(
                {
                    "detail": PASSWORD_CHANGE_REQUIRED_DETAIL,
                    "code": PASSWORD_CHANGE_REQUIRED_CODE,
                },
                status=403,
            )
        return redirect("/profile/password")


def _is_api_path(path_info: str) -> bool:
    return path_info == "/api" or path_info.startswith("/api/")


def _password_change_path_allowed(path: str, method: str) -> bool:
    if path in _ALLOWED_API_READS:
        return method in {"GET", "HEAD", "OPTIONS"}
    if path in _ALLOWED_API_PATHS or path in _ALLOWED_BROWSER_PATHS:
        return True
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _ALLOWED_BROWSER_PREFIXES
        if not prefix.endswith("/")
    ) or any(
        path.startswith(prefix)
        for prefix in _ALLOWED_BROWSER_PREFIXES
        if prefix.endswith("/")
    )


def _bounded_api_area(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[2][:32] if len(parts) > 2 else "unknown"


class UserWebSessionMiddleware:
    """
    Track authenticated Django web sessions via a companion `UserWebSession` row.

    This is tracking-only. Revocation still deletes rows from Django's session store.
    """

    # Simple write throttle: don't update last-seen more than once per minute unless
    # user agent / IP changes.
    THROTTLE_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if is_immutable_public_cover_path(request.path_info):
            return response

        try:
            user = getattr(request, "user", None)
            if not user or getattr(user, "is_anonymous", True):
                return response

            session = getattr(request, "session", None)
            if not session:
                return response

            session_key = getattr(session, "session_key", None) or ""
            if not session_key:
                # Avoid creating sessions unnecessarily.
                return response

            facts = get_browser_account_facts(request)
            if facts is None:
                return response

            user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:4000]
            ip_address = get_client_ip(request)

            now = timezone.now()
            defaults = {
                "user_id": facts.user_id,
                "user_agent": user_agent,
                "ip_address": ip_address,
            }

            obj, created = UserWebSession.objects.get_or_create(
                session_key=session_key,
                defaults=defaults,
            )

            if created:
                return response

            # Session keys can persist across logout/login; ensure ownership is correct.
            needs_save = False
            update_fields: list[str] = []

            if obj.user_id != facts.user_id:
                obj.user_id = facts.user_id
                needs_save = True
                update_fields.append("user")

            if (obj.user_agent or "") != user_agent:
                obj.user_agent = user_agent
                needs_save = True
                update_fields.append("user_agent")

            if obj.ip_address != ip_address:
                obj.ip_address = ip_address
                needs_save = True
                update_fields.append("ip_address")

            # Throttle last-seen updates.
            if obj.updated_at is None or (now - obj.updated_at) > timedelta(seconds=self.THROTTLE_SECONDS):
                needs_save = True

            if needs_save:
                # `updated_at` is auto_now; include it explicitly in update_fields so
                # Django performs an UPDATE even when only throttling.
                if "updated_at" not in update_fields:
                    update_fields.append("updated_at")
                obj.save(update_fields=update_fields)
        except Exception:
            # Best-effort tracking: do not block responses on tracking failures.
            return response

        return response
