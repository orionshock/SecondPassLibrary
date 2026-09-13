from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from library.groups.api_access import (
    authorize_book_assignment_mutation,
    normal_mutation_group_or_404,
)
from library.groups.book_assignment_serializers import (
    BookGroupAssignmentCreateSerializer,
    BookGroupAssignmentSerializer,
)
from library.groups.browse_views import GroupBookListView, GroupBrowseMixin
from library.groups.book_assignments import add_book_to_group, remove_book_from_group


class GroupBookAssignmentListView(GroupBookListView):
    assignment_serializer_class = BookGroupAssignmentSerializer

    def post(self, request, *args, **kwargs):
        group = normal_mutation_group_or_404(
            actor=request.user,
            group_id=self.kwargs[self.group_url_kwarg],
        )
        access = authorize_book_assignment_mutation(actor=request.user, group=group)
        serializer = BookGroupAssignmentCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        book = access.book_for_add(
            book_id=serializer.validated_data["book_id"],
        )
        assignment = add_book_to_group(book=book, group=group, actor=request.user)
        out = self.assignment_serializer_class(assignment)
        return Response(out.data, status=status.HTTP_201_CREATED)


class GroupBookAssignmentDetailView(GroupBrowseMixin, GenericAPIView):
    group_url_kwarg = "group_id"
    book_url_kwarg = "book_id"

    def delete(self, request, *args, **kwargs):
        group = normal_mutation_group_or_404(
            actor=request.user,
            group_id=self.kwargs[self.group_url_kwarg],
        )
        access = authorize_book_assignment_mutation(actor=request.user, group=group)
        book = access.book_for_removal(
            book_id=self.kwargs[self.book_url_kwarg],
        )
        try:
            remove_book_from_group(book=book, group=group, actor=request.user)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
