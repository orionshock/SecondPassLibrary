from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorViewSet, BookFileViewSet, BookMetadataViewSet, BookViewSet, SeriesViewSet

router = DefaultRouter()
router.register(r'authors', AuthorViewSet, basename='author')
router.register(r'series', SeriesViewSet, basename='series')
router.register(r'books', BookViewSet, basename='book')
router.register(r'book-files', BookFileViewSet, basename='bookfile')
router.register(r'book-metadata', BookMetadataViewSet, basename='bookmetadata')

urlpatterns = [
    path('', include(router.urls)),
]
