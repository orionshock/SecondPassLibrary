from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from accounts.services import user_supports_local_password


class ForcePasswordChangeMiddleware:
    """
    Product UI guardrail: if a user's profile requires a password change,
    redirect product UI pages to /profile/password/.

    This is intentionally scoped to product UI routes (not a full API lock).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path or "/"

        # Fast-path allowlist.
        if (
            path.startswith("/static/")
            or path.startswith("/admin/")
            or path.startswith("/api/")
            or path.startswith("/api-auth/")
            or path.startswith("/profile/password/")
        ):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or getattr(user, "is_anonymous", True):
            return self.get_response(request)

        try:
            profile = user.profile
        except Exception:
            return self.get_response(request)

        if (
            getattr(profile, "must_change_password", False)
            and user_supports_local_password(user)
        ):
            return redirect("/profile/password/")

        return self.get_response(request)
