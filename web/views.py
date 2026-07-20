from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from accounts import client_api
from accounts.bootstrap import (
    SetupAlreadyComplete,
    create_first_owner,
    has_active_owner,
)
from accounts.forms import FirstOwnerSetupForm


REACT_BUILD_MISSING_MESSAGE = (
    "React Product UI build is missing. Run 'npm.cmd run build' from web/react."
)


def index(request: HttpRequest) -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")
    return redirect("react_app")


def react_app(request: HttpRequest, react_path: str = "") -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")

    index_path = settings.REACT_UI_DIST_DIR / "index.html"
    try:
        index_html = index_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return HttpResponse(
            REACT_BUILD_MISSING_MESSAGE,
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    response = HttpResponse(index_html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


def login(request: HttpRequest) -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")
    return auth_views.LoginView.as_view(template_name="rest_framework/login.html")(
        request
    )


def setup(request: HttpRequest) -> HttpResponse:
    if has_active_owner():
        return redirect("login")

    form = FirstOwnerSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cleaned_data = cast(Mapping[str, Any], form.cleaned_data)
        try:
            create_first_owner(
                server_name=str(cleaned_data["server_name"]),
                server_description=str(cleaned_data.get("server_description", "")),
                public_group_name=str(cleaned_data["public_group_name"]),
                public_group_description=str(
                    cleaned_data.get("public_group_description", "")
                ),
                advanced_library_groups_enabled=bool(
                    cleaned_data.get("advanced_library_groups_enabled", False)
                ),
                username=str(cleaned_data["username"]),
                first_name=str(cleaned_data.get("first_name", "")),
                last_name=str(cleaned_data.get("last_name", "")),
                email=str(cleaned_data.get("email", "")),
                password=str(cleaned_data["password1"]),
            )
        except SetupAlreadyComplete:
            return redirect("login")
        except ValidationError as exc:
            error_dict = cast(Mapping[str, Any] | None, getattr(exc, "error_dict", None))
            if error_dict is not None:
                for field, errors in error_dict.items():
                    target = field if field in form.fields else None
                    for error in errors:
                        form.add_error(target, error)
            else:
                form.add_error(None, exc)
        else:
            return redirect("login")

    return render(request, "web/setup.html", {"form": form})


@login_required
def client_api_authorize(request: HttpRequest) -> HttpResponse:
    code = str(request.GET.get("code") or "").strip()
    client_name = ""
    message = ""
    error = ""
    login_request = None

    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip().lower()
        code = str(request.POST.get("code") or "").strip()
        raw_client_name = request.POST.get("client_name", None)
        client_name = str(raw_client_name or "").strip()
        login_request = client_api.get_pending_login_request_for_code(code)
        if not login_request:
            error = "Invalid or expired code."
        else:
            try:
                if action == "approve":
                    final_name = (
                        (login_request.client_name or "").strip()
                        if raw_client_name is None
                        else client_name
                    )
                    if not final_name:
                        error = "Device/client name is required."
                    elif len(final_name) > 200:
                        error = "Device/client name is too long."
                    else:
                        if final_name != login_request.client_name:
                            login_request.client_name = final_name
                            login_request.save(update_fields=["client_name", "updated_at"])
                        client_name = final_name
                        client_api.approve_login_request(
                            login_request=login_request, user=request.user
                        )
                        message = "Client authorized. Return to your reader."
                elif action == "deny":
                    client_api.deny_login_request(
                        login_request=login_request, user=request.user
                    )
                    message = "Client request denied."
                elif action != "lookup":
                    error = "Invalid action."
            except ValueError as exc:
                error = str(exc)

        return render(
            request,
            "web/client_api/authorize.html",
            {
                "code": client_api.format_human_code(code),
                "client_name": client_name,
                "login_request": login_request,
                "message": message,
                "error": error,
                "done": bool(message) and not bool(error),
            },
        )

    if code:
        login_request = client_api.get_pending_login_request_for_code(code)
        if not login_request:
            error = "Invalid or expired code."
        else:
            client_name = login_request.client_name

    return render(
        request,
        "web/client_api/authorize.html",
        {
            "code": client_api.format_human_code(code),
            "client_name": client_name,
            "login_request": login_request,
            "message": message,
            "error": error,
            "done": False,
        },
    )
