from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from library.models import Book

from .services import (
    export_all_marginalia,
    export_selected_marginalia,
    selected_book_sessions,
)


class PrettyJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = dict(renderer_context or {})
        renderer_context.setdefault("indent", 2)
        return super().render(data, accepted_media_type, renderer_context)


def _download_response(payload: dict, filename: str) -> Response:
    response = Response(payload)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class AllMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    renderer_classes = [PrettyJSONRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = export_all_marginalia(user=request.user)
        return _download_response(payload, "second-pass-marginalia.json")

    def post(self, request):
        selection = _parse_selection(data=request.data, user=request.user)
        payload = export_selected_marginalia(user=request.user, selection=selection)
        return _download_response(payload, "second-pass-marginalia.json")


def _parse_selection(*, data, user) -> list[dict]:
    raw_books = data.get("books") if isinstance(data, dict) else None
    if not isinstance(raw_books, list) or not raw_books:
        raise ValidationError({"books": ["Select at least one book or session."]})

    seen_books = set()
    selection = []
    for raw_book in raw_books:
        if not isinstance(raw_book, dict):
            raise ValidationError({"books": ["Each selected book must be an object."]})

        book_id = raw_book.get("book_id")
        if not book_id:
            raise ValidationError({"book_id": ["This field is required."]})
        if book_id in seen_books:
            raise ValidationError({"books": ["Duplicate book selections are not allowed."]})
        seen_books.add(book_id)

        book = get_object_or_404(
            Book.objects.select_related("series").prefetch_related("authors", "identifiers"),
            id=book_id,
        )

        raw_sessions = raw_book.get("sessions")
        if raw_sessions == "all":
            sessions = "all"
        elif isinstance(raw_sessions, list) and raw_sessions:
            try:
                sessions = selected_book_sessions(
                    user=user,
                    book=book,
                    session_ids=raw_sessions,
                )
            except (LookupError, TypeError, ValueError):
                raise NotFound() from None
        else:
            raise ValidationError({"sessions": ['Use "all" or a non-empty session list.']})

        selection.append({"book": book, "sessions": sessions})
    return selection
