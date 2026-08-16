from __future__ import annotations

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import is_librarian
from library.imports.batches import import_zip_file
from library.imports.epub import import_epub_file
from library.imports.results import ImportBatchResult
from library.imports.operational_logging import log_import_batch_completed
from library.imports.serializers import import_batch_payload


MAX_IMPORT_UPLOAD_BYTES = 256 * 1024 * 1024


class ImportUploadView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if not is_librarian(request.user):
            raise PermissionDenied("Not allowed to import books.")

        uploads = request.FILES.getlist("file")
        if not uploads:
            raise ValidationError({"file": ["Upload file is required."]})
        if len(uploads) > 1:
            raise ValidationError({"file": ["Upload exactly one file."]})

        upload = uploads[0]
        source_filename = upload.name or "upload"
        source_label = _safe_upload_label(source_filename)
        _validate_upload_size(upload)
        suffix = _upload_suffix(source_filename)
        if suffix == ".epub":
            result = _batch_from_epub_upload(
                upload,
                source_filename=source_label,
                actor=request.user,
            )
        elif suffix == ".zip":
            result = import_zip_file(upload, source_filename=source_label, actor=request.user)
        else:
            raise ValidationError({"file": ["Only .epub and .zip uploads are supported."]})

        log_import_batch_completed(
            result=result,
            actor=request.user,
            processed_bytes=getattr(upload, "size", None),
        )
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
    value = _safe_upload_label(filename)
    if "." not in value:
        return ""
    return f".{value.rsplit('.', 1)[-1].casefold()}"


def _safe_upload_label(filename: str) -> str:
    return (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1] or "upload"


def _validate_upload_size(upload) -> None:
    size = getattr(upload, "size", None)
    if size is not None and size > MAX_IMPORT_UPLOAD_BYTES:
        raise ValidationError({"file": ["Upload exceeds the import size limit."]})
