from django.urls import path

from library.catalog.views import BookDetailView, BookListView


app_name = "library"

urlpatterns = [
    path("books/", BookListView.as_view(), name="book-list"),
    path("books/<uuid:book_id>/", BookDetailView.as_view(), name="book-detail"),
]
