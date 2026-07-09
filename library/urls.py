from django.urls import path

from library.catalog.axis_views import (
    AuthorDetailView,
    AuthorListView,
    CatalogTagDetailView,
    CatalogTagListView,
    SeriesDetailView,
    SeriesListView,
)
from library.catalog.views import BookDetailView, BookListView


app_name = "library"

urlpatterns = [
    path("authors/", AuthorListView.as_view(), name="author-list"),
    path("authors/<uuid:axis_id>/", AuthorDetailView.as_view(), name="author-detail"),
    path("books/", BookListView.as_view(), name="book-list"),
    path("books/<uuid:book_id>/", BookDetailView.as_view(), name="book-detail"),
    path("series/", SeriesListView.as_view(), name="series-list"),
    path("series/<uuid:axis_id>/", SeriesDetailView.as_view(), name="series-detail"),
    path("tags/", CatalogTagListView.as_view(), name="tag-list"),
    path("tags/<uuid:axis_id>/", CatalogTagDetailView.as_view(), name="tag-detail"),
]
