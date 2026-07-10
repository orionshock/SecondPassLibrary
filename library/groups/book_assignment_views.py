from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from library import policies
from library.groups.book_assignment_serializers import (
    BookGroupAssignmentCreateSerializer,
    BookGroupAssignmentSerializer,
)
from library.groups.browse_views import GroupBookListView, GroupBrowseMixin
from library.groups.services import add_book_to_group, remove_book_from_group
from library.models import Book
from library.queries import can_manage_library


class GroupBookAssignmentListView(GroupBookListView):
    assignment_serializer_class = BookGroupAssignmentSerializer

    def post(self, request, *args, **kwargs):
        group = self.get_group()
        serializer = BookGroupAssignmentCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        book = _visible_mutation_book_or_404(
            user=request.user,
            book_id=serializer.validated_data["book_id"],
        )
        if not policies.can_add_book_to_group(user=request.user, book=book, group=group):
            raise PermissionDenied("Not allowed to add books to this group.")
        assignment = add_book_to_group(book=book, group=group, actor=request.user)
        out = self.assignment_serializer_class(assignment)
        return Response(out.data, status=status.HTTP_201_CREATED)


class GroupBookAssignmentDetailView(GroupBrowseMixin, GenericAPIView):
    group_url_kwarg = "group_id"
    book_url_kwarg = "book_id"

    def delete(self, request, *args, **kwargs):
        group = self.get_group()
        book = _visible_mutation_book_or_404(
            user=request.user,
            book_id=self.kwargs[self.book_url_kwarg],
        )
        if not policies.can_remove_book_from_group(user=request.user, book=book, group=group):
            raise PermissionDenied("Not allowed to remove books from this group.")
        try:
            remove_book_from_group(book=book, group=group, actor=request.user)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _visible_mutation_book_or_404(*, user, book_id) -> Book:
    try:
        book = Book.objects.get(pk=book_id)
    except Book.DoesNotExist as exc:
        raise Http404 from exc
    if can_manage_library(user):
        return book
    if not policies.can_view_book(user=user, book=book):
        raise Http404
    return book
