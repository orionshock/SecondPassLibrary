from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, cast
from uuid import UUID

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.http import Http404
from django.shortcuts import redirect, render

from accounts import client_api
from accounts.bootstrap import (
    SetupAlreadyComplete,
    create_first_owner,
    has_active_owner,
)
from accounts.forms import FirstOwnerSetupForm
from accounts import policies as account_policies
from library import policies as library_policies
from core import server_settings as server_settings_service
from library.models import Book
from reading.services import list_sessions_for_book, list_sessions_for_user
from reading.models import ReadingSession


def _uuid_or_404(value: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise Http404() from None


def product_login_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    login_view = cast(Callable[..., HttpResponse], login_required(view_func))

    @wraps(view_func)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not has_active_owner():
            return redirect("web:setup")
        return login_view(request, *args, **kwargs)

    return wrapped


def index(request: HttpRequest) -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")
    return redirect("/dashboard/")


def login(request: HttpRequest) -> HttpResponse:
    if not has_active_owner():
        return redirect("web:setup")
    return auth_views.LoginView.as_view(
        template_name="rest_framework/login.html"
    )(request)


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


@product_login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "web/dashboard/app.html",
        {"server_banner_message": server_settings_service.get_server_banner_message()},
    )


@product_login_required
def reading_sessions(request: HttpRequest) -> HttpResponse:
    sessions = list_sessions_for_user(user=request.user)
    return render(request, "web/reading/sessions.html", {"sessions": sessions})


@product_login_required
def reading_export(request: HttpRequest) -> HttpResponse:
    rows_by_book: dict[str, dict] = {}
    for row in list_sessions_for_user(user=request.user):
        book = cast(Mapping[str, Any], row.get("book") or {})
        book_id = str(book.get("id") or "")
        if not book_id:
            continue
        entry = rows_by_book.setdefault(
            book_id,
            {
                "id": book_id,
                "title": book.get("title") or "Book unavailable",
                "authors": book.get("authors") or [],
                "series_name": book.get("series_name") or "",
                "series_index": book.get("series_index"),
                "cover_url": book.get("cover_url") or "",
                "session_count": 0,
                "annotation_count": 0,
                "sessions": [],
            },
        )
        entry["session_count"] += 1
        entry["annotation_count"] += int(row.get("annotation_count") or 0)
        entry["sessions"].append(row)

    books = sorted(rows_by_book.values(), key=lambda b: str(b.get("title") or "").lower())
    return render(request, "web/reading/export.html", {"books": books})


@product_login_required
def reading_import(request: HttpRequest) -> HttpResponse:
    return render(request, "web/reading/import.html")


@product_login_required
def reading_session_marginalia(
    request: HttpRequest, book_id: str, session_id: str
) -> HttpResponse:
    book_uuid = _uuid_or_404(book_id)
    session_uuid = _uuid_or_404(session_id)
    session = (
        ReadingSession.objects.select_related("book")
        .filter(id=session_uuid, user=request.user)
        .first()
    )
    if session is None:
        raise Http404()
    if session.book_id != book_uuid:
        raise Http404()

    return render(
        request,
        "web/reading/book_activity.html",
        {
            "book_id": str(book_uuid),
            "session_id": str(session_uuid),
            "can_open": library_policies.can_view_book(user=request.user, book=session.book),
        },
    )


@product_login_required
def reading_book_sessions_canonical(request: HttpRequest, book_id: str) -> HttpResponse:
    book_uuid = _uuid_or_404(book_id)
    book = (
        Book.objects.select_related("series")
        .prefetch_related("authors")
        .filter(id=book_uuid)
        .first()
    )
    if book is None:
        raise Http404()
    if not library_policies.can_view_book(user=request.user, book=book):
        raise Http404()

    sessions = list_sessions_for_book(user=request.user, book=book)
    recent_session_id = sessions[0]["id"] if sessions else ""

    return render(
        request,
        "web/reading/book_sessions.html",
        {"book": book, "sessions": sessions, "recent_session_id": recent_session_id},
    )

@product_login_required
def library_browse(request: HttpRequest) -> HttpResponse:
    return render(request, "web/library/library.html")


@product_login_required
def book_detail(request: HttpRequest, book_id: str) -> HttpResponse:
    book_uuid = _uuid_or_404(book_id)
    return render(request, "web/library/book_detail.html", {"book_id": str(book_uuid)})


@product_login_required
def book_edit(request: HttpRequest, book_id: str) -> HttpResponse:
    book_uuid = _uuid_or_404(book_id)
    return render(request, "web/library/book_edit.html", {"book_id": str(book_uuid)})


@product_login_required
def imports(request: HttpRequest) -> HttpResponse:
    return render(request, "web/imports/imports.html")


@product_login_required
def groups(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups/groups.html")


@product_login_required
def group_detail(request: HttpRequest, group_id: str) -> HttpResponse:
    group_uuid = _uuid_or_404(group_id)
    return render(request, "web/groups/detail.html", {"group_id": str(group_uuid)})


@product_login_required
def group_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups/new.html")


@product_login_required
def group_edit(request: HttpRequest, group_id: str) -> HttpResponse:
    group_uuid = _uuid_or_404(group_id)
    return render(request, "web/groups/edit.html", {"group_id": str(group_uuid)})


@product_login_required
def users(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users/users.html")


@product_login_required
def user_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users/new.html")


@product_login_required
def user_edit(request: HttpRequest, profile_id: str) -> HttpResponse:
    profile_uuid = _uuid_or_404(profile_id)
    return render(request, "web/users/edit.html", {"profile_id": str(profile_uuid)})


@product_login_required
def shelves(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelves/shelves.html")


@product_login_required
def shelf_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelves/new.html")


@product_login_required
def shelf_detail(request: HttpRequest, shelf_id: str) -> HttpResponse:
    shelf_uuid = _uuid_or_404(shelf_id)
    return render(request, "web/shelves/detail.html", {"shelf_id": str(shelf_uuid)})


@product_login_required
def shelf_edit(request: HttpRequest, shelf_id: str) -> HttpResponse:
    shelf_uuid = _uuid_or_404(shelf_id)
    return render(request, "web/shelves/edit.html", {"shelf_id": str(shelf_uuid)})


@product_login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile/profile.html")


@product_login_required
def profile_password(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile/password.html")


@product_login_required
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
                    # Allow user to edit the client name during approval.
                    if raw_client_name is None:
                        # Backwards-compatible: if the form field was not sent, keep the
                        # existing request client_name.
                        final_name = (login_request.client_name or "").strip()
                    else:
                        # If the field was present, treat empty/whitespace as invalid.
                        final_name = (client_name or "").strip()

                    if not final_name:
                        error = "Device/client name is required."
                    elif len(final_name) > 200:
                        error = "Device/client name is too long."
                    else:
                        if final_name != login_request.client_name:
                            login_request.client_name = final_name
                            login_request.save(update_fields=["client_name", "updated_at"])
                        client_name = final_name

                    if not error:
                        client_api.approve_login_request(
                            login_request=login_request, user=request.user
                        )
                        message = "Client authorized. Return to your reader."
                elif action == "deny":
                    client_api.deny_login_request(
                        login_request=login_request, user=request.user
                    )
                    message = "Client request denied."
                elif action == "lookup":
                    # No-op: just render the request details for confirmation.
                    pass
                else:
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


@product_login_required
def server_settings(request: HttpRequest) -> HttpResponse:
    if not account_policies.is_owner(getattr(request, "user", None)):
        raise PermissionDenied
    return render(request, "web/server/settings.html")
