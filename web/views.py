from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render


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
def imports(request: HttpRequest) -> HttpResponse:
    return render(request, "web/imports.html")


@login_required
def groups(request: HttpRequest) -> HttpResponse:
    return render(request, "web/groups.html")


@login_required
def group_detail(request: HttpRequest, group_id: str) -> HttpResponse:
    return render(request, "web/group_detail.html", {"group_id": group_id})


@login_required
def users(request: HttpRequest) -> HttpResponse:
    return render(request, "web/users.html")


@login_required
def user_new(request: HttpRequest) -> HttpResponse:
    return render(request, "web/user_new.html")
