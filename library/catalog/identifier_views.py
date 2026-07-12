from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import is_librarian
from library.catalog.edit_services import create_book_identifier, update_book_identifier
from library.catalog.serializers import BookIdentifierSerializer, BookIdentifierWriteSerializer
from library.models import BookIdentifier
from library.queries import visible_books_for_user


def _visible_book(request, book_id):
    return get_object_or_404(visible_books_for_user(request.user, cached=False), pk=book_id)


def _require_editor(request) -> None:
    if not is_librarian(request.user):
        raise PermissionDenied("Not allowed.")


def _raise_validation(exc: DjangoValidationError) -> None:
    raise serializers.ValidationError(
        exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    ) from exc


class BookIdentifierListCreateView(APIView):
    def get(self, request, book_id):
        book = _visible_book(request, book_id)
        return Response(BookIdentifierSerializer(book.identifiers.all(), many=True).data)

    def post(self, request, book_id):
        _require_editor(request)
        book = _visible_book(request, book_id)
        serializer = BookIdentifierWriteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            identifier = create_book_identifier(book=book, **serializer.validated_data)
        except DjangoValidationError as exc:
            _raise_validation(exc)
        return Response(BookIdentifierSerializer(identifier).data, status=status.HTTP_201_CREATED)


class BookIdentifierDetailView(APIView):
    def _object(self, request, book_id, identifier_id):
        book = _visible_book(request, book_id)
        return get_object_or_404(BookIdentifier, pk=identifier_id, book=book)

    def patch(self, request, book_id, identifier_id):
        _require_editor(request)
        identifier = self._object(request, book_id, identifier_id)
        serializer = BookIdentifierWriteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            identifier = update_book_identifier(identifier=identifier, **serializer.validated_data)
        except DjangoValidationError as exc:
            _raise_validation(exc)
        return Response(BookIdentifierSerializer(identifier).data)

    def delete(self, request, book_id, identifier_id):
        _require_editor(request)
        self._object(request, book_id, identifier_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
