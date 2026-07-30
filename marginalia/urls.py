from django.urls import path

from .views import (
    MarginaliaBookDetailView,
    MarginaliaBookListView,
    MarginaliaBookSessionListView,
)


app_name = "marginalia"

urlpatterns = [
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
