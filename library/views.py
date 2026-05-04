from django.http import FileResponse, Http404
from django.db.models import Prefetch

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import Author, Book, BookFile, Series, BookIdentifier
from .serializers import (
    AuthorSerializer,
    BookFileSerializer,
    BookSerializer,
    SeriesSerializer,
    ImportJobSerializer,
)
from .services import (
    generate_epub_download_filename,
    create_import_job_from_upload,
    process_import_job,
)
from .models import ImportJob


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]


class BookViewSet(viewsets.ModelViewSet):
    queryset = (
        Book.objects.select_related("series")
        .prefetch_related(
            Prefetch("authors", queryset=Author.objects.order_by("name")),
            Prefetch("files", queryset=BookFile.objects.order_by("created_at")),
            Prefetch(
                "identifiers",
                queryset=BookIdentifier.objects.order_by("scheme", "value"),
            ),
        )
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


class ImportJobViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ImportJobSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ImportJob.objects.prefetch_related("items").filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {"detail": 'Missing multipart upload field "file".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job = create_import_job_from_upload(user=request.user, uploaded_file=uploaded)
            job = process_import_job(job=job)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
