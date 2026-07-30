from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from accounts.authentication import ClientBearerAuthentication

from .queries import marginalia_books_for_user
from .serializers import MarginaliaBookSummarySerializer


class MarginaliaBookReadMixin:
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = MarginaliaBookSummarySerializer

    def get_queryset(self):
        return marginalia_books_for_user(user=self.request.user)


class MarginaliaBookListView(MarginaliaBookReadMixin, ListAPIView):
    def get_queryset(self):
        return marginalia_books_for_user(
            user=self.request.user,
            q=self.request.query_params.get("q", ""),
        )


class MarginaliaBookDetailView(MarginaliaBookReadMixin, RetrieveAPIView):
    lookup_url_kwarg = "book_id"
