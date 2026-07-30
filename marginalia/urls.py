from django.urls import path

from .views import MarginaliaBookDetailView, MarginaliaBookListView


app_name = "marginalia"

urlpatterns = [
    path("books/", MarginaliaBookListView.as_view(), name="book-list"),
    path(
        "books/<uuid:book_id>/",
        MarginaliaBookDetailView.as_view(),
        name="book-detail",
    ),
]
