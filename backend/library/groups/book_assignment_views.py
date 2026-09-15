from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from library.groups.api_access import normal_book_assignment_group_or_404
from library.groups.book_assignment_serializers import (
    BookGroupAssignmentCreateSerializer,
    BookGroupAssignmentSerializer,
)
from library.groups.browse_views import GroupBookListView, GroupBrowseMixin
from library.groups.book_assignment_workflows import (
    create_normal_book_assignment,
    remove_normal_book_assignment,
)


class GroupBookAssignmentListView(GroupBookListView):
    assignment_serializer_class = BookGroupAssignmentSerializer

    def post(self, request, *args, **kwargs):
        normal_book_assignment_group_or_404(
            actor=request.user,
            group_id=self.kwargs[self.group_url_kwarg],
        )
        serializer = BookGroupAssignmentCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        assignment = create_normal_book_assignment(
            actor=request.user,
            group_id=self.kwargs[self.group_url_kwarg],
            book_id=serializer.validated_data["book_id"],
        )
        out = self.assignment_serializer_class(assignment)
        return Response(out.data, status=status.HTTP_201_CREATED)


class GroupBookAssignmentDetailView(GroupBrowseMixin, GenericAPIView):
    group_url_kwarg = "group_id"
    book_url_kwarg = "book_id"

    def delete(self, request, *args, **kwargs):
        try:
            remove_normal_book_assignment(
                actor=request.user,
                group_id=self.kwargs[self.group_url_kwarg],
                book_id=self.kwargs[self.book_url_kwarg],
            )
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
