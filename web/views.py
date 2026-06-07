from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseForbidden
from django.http import Http404
from django.shortcuts import redirect, render

from accounts import client_api
from core import policies
from library.models import Book
from reading.services import list_sessions_for_book, list_sessions_for_user
from reading.models import ReadingSession


def index(request: HttpRequest) -> HttpResponse:
    return redirect("/app/")


@login_required
def app_dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "web/dashboard/app.html")


@login_required
def reading_sessions(request: HttpRequest) -> HttpResponse:
    sessions = list_sessions_for_user(user=request.user)
    return render(request, "web/reading/sessions.html", {"sessions": sessions})


@login_required
def reading_export(request: HttpRequest) -> HttpResponse:
    rows_by_book: dict[str, dict] = {}
    for row in list_sessions_for_user(user=request.user):
        book = row.get("book") or {}
        book_id = str(book.get("id") or "")
        if not book_id:
            continue
        entry = rows_by_book.setdefault(
            book_id,
            {
                "id": book_id,
                "title": book.get("title") or "Book",
                "authors": book.get("authors") or [],
                "cover_url": book.get("cover_url") or "",
                "session_count": 0,
                "annotation_count": 0,
            },
        )
        entry["session_count"] += 1
        entry["annotation_count"] += int(row.get("annotation_count") or 0)

    books = sorted(rows_by_book.values(), key=lambda b: str(b.get("title") or "").lower())
    return render(request, "web/reading/export.html", {"books": books})


@login_required
def reading_session_marginalia(
    request: HttpRequest, book_id: str, session_id: str
) -> HttpResponse:
    session = (
        ReadingSession.objects.select_related("book")
        .filter(id=session_id, user=request.user)
        .first()
    )
    if session is None:
        raise Http404()
    if str(session.book_id) != str(book_id):
        raise Http404()
    if not policies.can_view_book(user=request.user, book=session.book):
        raise Http404()

    return render(
        request,
        "web/reading/book_activity.html",
        {"book_id": str(book_id), "session_id": str(session_id)},
    )


@login_required
def reading_book_activity_legacy(request: HttpRequest, book_id: str) -> HttpResponse:
    book = Book.objects.filter(id=book_id).first()
    if book is None:
        raise Http404()
    if not policies.can_view_book(user=request.user, book=book):
        raise Http404()

    preferred = str(request.GET.get("session") or "").strip()
    if preferred:
        return redirect(f"/reading/sessions/books/{book_id}/{preferred}/", permanent=False)

    sessions = list_sessions_for_book(user=request.user, book=book)
    if sessions:
        return redirect(
            f"/reading/sessions/books/{book_id}/{sessions[0]['id']}/", permanent=False
        )
    return redirect(f"/reading/sessions/books/{book_id}/", permanent=False)


@login_required
def reading_book_sessions_canonical(request: HttpRequest, book_id: str) -> HttpResponse:
    book = (
        Book.objects.select_related("series")
        .prefetch_related("authors")
        .filter(id=book_id)
        .first()
    )
    if book is None:
        raise Http404()
    if not policies.can_view_book(user=request.user, book=book):
        raise Http404()

    sessions = list_sessions_for_book(user=request.user, book=book)
    recent_session_id = sessions[0]["id"] if sessions else ""

    return render(
        request,
        "web/reading/book_sessions.html",
        {"book": book, "sessions": sessions, "recent_session_id": recent_session_id},
    )


@login_required
def reading_book_sessions_legacy(request: HttpRequest, book_id: str) -> HttpResponse:
    # Development redirect to the canonical sessions-first route family.
    return redirect(f"/reading/sessions/books/{book_id}/", permanent=False)

@login_required
def library_browse(request: HttpRequest) -> HttpResponse:
    return render(request, "web/library/library.html")


@login_required
def book_detail(request: HttpRequest, book_id: str) -> HttpResponse:
    return render(request, "web/library/book_detail.html", {"book_id": book_id})


@login_required
def book_edit(request: HttpRequest, book_id: str) -> HttpResponse:
    return render(request, "web/library/book_edit.html", {"book_id": book_id})


@login_required
def imports(request: HttpRequest) -> HttpResponse:
    return render(request, "web/imports/imports.html")


@login_required
def groups(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups/groups.html")


@login_required
def group_detail(request: HttpRequest, group_id: str) -> HttpResponse:
    return render(request, "web/groups/detail.html", {"group_id": group_id})


@login_required
def group_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups/new.html")


@login_required
def group_edit(request: HttpRequest, group_id: str) -> HttpResponse:
    return render(request, "web/groups/edit.html", {"group_id": group_id})


@login_required
def users(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users/users.html")


@login_required
def user_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users/new.html")


@login_required
def user_edit(request: HttpRequest, user_id: str) -> HttpResponse:
    return render(request, "web/users/edit.html", {"user_id": user_id})


@login_required
def shelves(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelves/shelves.html")


@login_required
def shelf_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/shelves/new.html")


@login_required
def shelf_detail(request: HttpRequest, shelf_id: str) -> HttpResponse:
    return render(request, "web/shelves/detail.html", {"shelf_id": shelf_id})


@login_required
def shelf_edit(request: HttpRequest, shelf_id: str) -> HttpResponse:
    return render(request, "web/shelves/edit.html", {"shelf_id": shelf_id})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile/profile.html")


@login_required
def profile_password(request: HttpRequest) -> HttpResponse:
    return render(request, "web/profile/password.html")


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


@login_required
def server_settings(request: HttpRequest) -> HttpResponse:
    if not policies.is_owner(getattr(request, "user", None)):
        return HttpResponseForbidden("Not allowed.")
    return render(request, "web/server/settings.html")
