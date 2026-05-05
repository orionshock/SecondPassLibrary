from django.http import FileResponse, Http404
from django.db.models import Prefetch
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

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
from .group_services import ensure_book_public_assignment
from core import policies


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(books__group_assignments__group__memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(books__group_assignments__group__memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()


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
    ordering_fields = ["title", "created_at", "updated_at", "published_date"]
    ordering = ["title", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.request

        if not policies.can_manage_library(request.user):
            queryset = queryset.filter(
                group_assignments__group__memberships__user=request.user
            )

        q = (request.query_params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(subtitle__icontains=q)
                | Q(authors__name__icontains=q)
                | Q(series__name__icontains=q)
                | Q(isbn__icontains=q)
                | Q(identifiers__value__icontains=q)
            )

        author_id = (request.query_params.get("author") or "").strip()
        if author_id:
            queryset = queryset.filter(authors__id=author_id)

        series_id = (request.query_params.get("series") or "").strip()
        if series_id:
            queryset = queryset.filter(series__id=series_id)

        language = (request.query_params.get("language") or "").strip()
        if language:
            queryset = queryset.filter(language__iexact=language)

        has_files = (request.query_params.get("has_files") or "").strip().lower()
        if has_files in {"true", "1", "yes", "y", "on"}:
            queryset = queryset.filter(files__isnull=False)
        elif has_files in {"false", "0", "no", "n", "off"}:
            queryset = queryset.filter(files__isnull=True)

        ordering = (request.query_params.get("ordering") or "").strip()
        if ordering:
            field = ordering.lstrip("-")
            if field in set(self.ordering_fields):
                queryset = queryset.order_by(ordering, "created_at")
        return queryset.distinct()

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        book = serializer.save()
        ensure_book_public_assignment(book=book, added_by=self.request.user)

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()


class BookFileViewSet(viewsets.ModelViewSet):
    queryset = (
        BookFile.objects.select_related("book", "book__series")
        .prefetch_related("book__authors")
        .all()
    )
    serializer_class = BookFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(book__group_assignments__group__memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        book_file: BookFile = self.get_object()

        if not policies.can_download_book_file(user=request.user, book_file=book_file):
            raise PermissionDenied("Not allowed.")

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
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        base = ImportJob.objects.prefetch_related("items")
        if policies.can_manage_library(self.request.user):
            return base.all()
        return base.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if not policies.can_import_books(request.user):
            raise PermissionDenied("Not allowed.")
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
