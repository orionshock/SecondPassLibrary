from django.http import FileResponse, Http404

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import Author, Book, BookFile, Series
from .serializers import (
    AuthorSerializer,
    BookFileSerializer,
    BookSerializer,
    SeriesSerializer,
)
from .services import generate_epub_download_filename


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
    queryset = (
        BookFile.objects.select_related("book", "book__series")
        .prefetch_related("book__authors")
        .all()
    )
    serializer_class = BookFileSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        book_file: BookFile = self.get_object()

        if not book_file.file:
            raise Http404("Stored file missing.")

        storage = book_file.file.storage
        name = book_file.file.name
        if not storage.exists(name):
            raise Http404("Stored file missing.")

        download_name = generate_epub_download_filename(book=book_file.book)
        file_handle = storage.open(name, "rb")
        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=download_name,
            content_type="application/epub+zip",
        )

