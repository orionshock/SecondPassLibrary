from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import is_librarian
from library.catalog.serializers import BookDetailSerializer
from library.catalog.views import book_browse_queryset
from library.cover_services import (
    InvalidBookCover,
    clear_book_cover,
    replace_book_cover,
    validate_book_cover_upload,
)
from library.queries import visible_books_for_user


class BookCoverView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, book_id):
        book = self._get_book(request.user, book_id)
        self._require_librarian(request.user)
        upload = request.FILES.get("cover")
        if upload is None:
            raise ValidationError({"cover": ["Choose a cover image."]})
        try:
            cover = validate_book_cover_upload(upload)
        except InvalidBookCover as exc:
            raise ValidationError({"cover": [str(exc)]}) from exc
        replace_book_cover(book=book, cover=cover, actor=request.user)
        return self._book_response(request, book_id)

    def delete(self, request, book_id):
        book = self._get_book(request.user, book_id)
        self._require_librarian(request.user)
        clear_book_cover(book=book, actor=request.user)
        return self._book_response(request, book_id)

    @staticmethod
    def _get_book(user, book_id):
        book = visible_books_for_user(user, cached=False).filter(pk=book_id).first()
        if book is None:
            raise Http404
        return book

    @staticmethod
    def _require_librarian(user) -> None:
        if not is_librarian(user):
            raise PermissionDenied("Not allowed.")

    @staticmethod
    def _book_response(request, book_id):
        book = book_browse_queryset(visible_books_for_user(request.user, cached=False)).get(
            pk=book_id
        )
        payload = BookDetailSerializer(book, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)
