from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthorViewSet,
    BookFileViewSet,
    BookViewSet,
    ImportJobViewSet,
    LibraryGroupViewSet,
    SeriesViewSet,
)

app_name = "library"

router = DefaultRouter()
router.register(r"authors", AuthorViewSet, basename="author")
router.register(r"series", SeriesViewSet, basename="series")
router.register(r"books", BookViewSet, basename="book")
router.register(r"book-files", BookFileViewSet, basename="bookfile")
router.register(r"imports", ImportJobViewSet, basename="importjob")
router.register(r"groups", LibraryGroupViewSet, basename="librarygroup")

urlpatterns = [
    path("", include(router.urls)),
]
