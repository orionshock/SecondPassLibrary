from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from accounts.bootstrap import (
    SetupAlreadyComplete,
    create_first_owner,
    has_active_owner,
)
from accounts.forms import FirstOwnerSetupForm


REACT_BUILD_MISSING_MESSAGE = (
    "React Product UI build is missing. Run 'npm.cmd run build' from web/react."
)


def react_app(request: HttpRequest, react_path: str = "") -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url="login")

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
