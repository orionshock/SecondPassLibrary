from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .api import MarginaliaReadMixin
from .queries import (
    marginalia_books_for_user,
    marginalia_sessions_for_book,
    marginalia_sessions_for_user,
)
from .serializers import (
    MarginaliaBookSummarySerializer,
    MarginaliaGlobalSessionSummarySerializer,
    MarginaliaSessionSummarySerializer,
)


class MarginaliaBookReadMixin(MarginaliaReadMixin):
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


class MarginaliaBookSessionListView(MarginaliaBookReadMixin, ListAPIView):
    serializer_class = MarginaliaSessionSummarySerializer

    def get_parent_book(self):
        if not hasattr(self, "_parent_book"):
            self._parent_book = get_object_or_404(
                marginalia_books_for_user(user=self.request.user),
                pk=self.kwargs["book_id"],
            )
        return self._parent_book

    def get_queryset(self):
        return marginalia_sessions_for_book(
            user=self.request.user,
            book=self.get_parent_book(),
            status=self.request.query_params.get("status", ""),
            q=self.request.query_params.get("q", ""),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        results = response.data.pop("results")
        response.data["context"] = {
            "book": MarginaliaBookSummarySerializer(
                self.get_parent_book(),
                context={"request": request},
            ).data
        }
        response.data["results"] = results
        return response


class MarginaliaSessionListView(MarginaliaReadMixin, ListAPIView):
    serializer_class = MarginaliaGlobalSessionSummarySerializer

    def get_queryset(self):
        return marginalia_sessions_for_user(
            user=self.request.user,
            status=self.request.query_params.get("status", ""),
            q=self.request.query_params.get("q", ""),
        )
