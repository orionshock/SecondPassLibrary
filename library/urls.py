from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .catalog.views import AuthorViewSet, BookViewSet, SeriesViewSet
from .file_views import BookFileViewSet
from .groups.views import LibraryGroupViewSet
from .imports.views import ImportViewSet

app_name = "library"

router = DefaultRouter()
router.register(r"authors", AuthorViewSet, basename="author")
router.register(r"series", SeriesViewSet, basename="series")
router.register(r"books", BookViewSet, basename="book")
router.register(r"book-files", BookFileViewSet, basename="bookfile")
router.register(r"imports", ImportViewSet, basename="import")
router.register(r"groups", LibraryGroupViewSet, basename="librarygroup")

urlpatterns = [
    path("", include(router.urls)),
]
