from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import is_librarian
from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.imports.results import ImportBatchResult
from library.imports.serializers import import_batch_payload


class ImportUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed to import books.")

        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Upload file is required."]})

        source_filename = upload.name or "upload"
        suffix = _upload_suffix(source_filename)
        if suffix == ".epub":
            result = _batch_from_epub_upload(
                upload,
                source_filename=source_filename,
                actor=request.user,
            )
        elif suffix == ".zip":
            result = import_zip_file(upload, source_filename=source_filename, actor=request.user)
        else:
            raise ValidationError({"file": ["Only .epub and .zip uploads are supported."]})

        return Response(import_batch_payload(result), status=status.HTTP_200_OK)


def _batch_from_epub_upload(upload, *, source_filename: str, actor) -> ImportBatchResult:
    item = import_epub_file(upload, source_filename=source_filename, actor=actor)
    return ImportBatchResult(
        source_type="epub",
        source_label=source_filename,
        items=[item],
        discovered_count=1,
    )


def _upload_suffix(filename: str) -> str:
    value = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in value:
        return ""
    return f".{value.rsplit('.', 1)[-1].casefold()}"
