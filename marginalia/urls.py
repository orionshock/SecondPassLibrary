from django.urls import path

from .detail_views import MarginaliaSessionDetailView
from .views import (
    MarginaliaBookDetailView,
    MarginaliaBookListView,
    MarginaliaBookSessionListView,
    MarginaliaSessionListView,
)


app_name = "marginalia"

urlpatterns = [
    path("sessions/", MarginaliaSessionListView.as_view(), name="session-list"),
    path(
        "sessions/<uuid:session_id>/",
        MarginaliaSessionDetailView.as_view(),
        name="session-detail",
    ),
    path("books/", MarginaliaBookListView.as_view(), name="book-list"),
    path(
        "books/<uuid:book_id>/sessions/",
        MarginaliaBookSessionListView.as_view(),
        name="book-session-list",
    ),
    path(
        "books/<uuid:book_id>/",
        MarginaliaBookDetailView.as_view(),
        name="book-detail",
    ),
]
