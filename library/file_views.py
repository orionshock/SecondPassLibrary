from django.http import FileResponse, Http404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from core import policies

from .catalog_serializers import BookFileSerializer
from .models import BookFile
from .services import generate_epub_download_filename
from .view_mixins import ClientBearerReadOnlyMixin

class BookFileViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}, "download": {"GET"}}
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


