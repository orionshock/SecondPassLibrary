from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Author, Book, BookFile, BookMetadata, Series
from .serializers import (
    AuthorSerializer,
    BookFileSerializer,
    BookMetadataSerializer,
    BookSerializer,
    SeriesSerializer,
)


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.prefetch_related("authors", "files").select_related(
        "series"
    )
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticated]


class BookFileViewSet(viewsets.ModelViewSet):
    queryset = BookFile.objects.select_related("book").all()
    serializer_class = BookFileSerializer
    permission_classes = [IsAuthenticated]


class BookMetadataViewSet(viewsets.ModelViewSet):
    queryset = BookMetadata.objects.select_related("book").all()
    serializer_class = BookMetadataSerializer
    permission_classes = [IsAuthenticated]
