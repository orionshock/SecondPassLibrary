from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from accounts import client_api
from core import policies


def index(request: HttpRequest) -> HttpResponse:
    return redirect("/app/")


@login_required
def app_dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "web/app.html")


@login_required
def library_browse(request: HttpRequest) -> HttpResponse:
    return render(request, "web/library.html")


@login_required
def book_detail(request: HttpRequest, book_id: str) -> HttpResponse:
    return render(request, "web/book_detail.html", {"book_id": book_id})


@login_required
def book_edit(request: HttpRequest, book_id: str) -> HttpResponse:
    return render(request, "web/book_edit.html", {"book_id": book_id})


@login_required
def imports(request: HttpRequest) -> HttpResponse:
    return render(request, "web/imports.html")


@login_required
def groups(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups.html")


@login_required
def group_detail(request: HttpRequest, group_id: str) -> HttpResponse:
    return render(request, "web/group_detail.html", {"group_id": group_id})


@login_required
def group_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/group_new.html")


@login_required
def group_edit(request: HttpRequest, group_id: str) -> HttpResponse:
    return render(request, "web/group_edit.html", {"group_id": group_id})


@login_required
def users(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users.html")


@login_required
def user_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/user_new.html")


@login_required
def user_edit(request: HttpRequest, user_id: str) -> HttpResponse:
    return render(request, "web/user_edit.html", {"user_id": user_id})


@login_required
def shelves(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelves.html")


@login_required
def shelf_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelf_new.html")


@login_required
def shelf_detail(request: HttpRequest, shelf_id: str) -> HttpResponse:
    return render(request, "web/shelf_detail.html", {"shelf_id": shelf_id})


@login_required
def shelf_edit(request: HttpRequest, shelf_id: str) -> HttpResponse:
    return render(request, "web/shelf_edit.html", {"shelf_id": shelf_id})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile.html")


@login_required
def profile_password(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile_password.html")


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
            "web/client_api_authorize.html",
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
        "web/client_api_authorize.html",
        {
            "code": client_api.format_human_code(code),
            "client_name": client_name,
            "login_request": login_request,
            "message": message,
            "error": error,
            "done": False,
        },
    )


@login_required
def server_settings(request: HttpRequest) -> HttpResponse:
    if not policies.is_owner(getattr(request, "user", None)):
        return HttpResponseForbidden("Not allowed.")
    return render(request, "web/server_settings.html")
