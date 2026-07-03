from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from library import policies
from core.errors import ErrorCode, api_error_response

from .catalog_serializers import ImportJobSerializer
from .models import ImportJob
from .import_services import ImportResourceLimitError
from .services import create_import_job_from_upload, process_import_job
from .view_mixins import ClientBearerReadOnlyMixin

class ImportJobViewSet(
    ClientBearerReadOnlyMixin,
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # Client bearer tokens should not be usable for imports (even read).
    client_bearer_allowed: dict[str, set[str]] = {}
    serializer_class = ImportJobSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        return ImportJob.objects.prefetch_related("items").all()

    def create(self, request, *args, **kwargs):
        if not policies.can_import_books(request.user):
            raise PermissionDenied("Not allowed.")
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return api_error_response(
                code=ErrorCode.MISSING_UPLOAD_FILE,
                message='Missing multipart upload field "file".',
                hint='Send a multipart/form-data request with a "file" field containing a .epub or .zip.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        job = None
        try:
            job = create_import_job_from_upload(user=request.user, uploaded_file=uploaded)
            job = process_import_job(job=job)
        except ImportResourceLimitError as e:
            if job is not None:
                job.delete()
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Import upload exceeds resource limits.",
                detail=str(e),
                hint="Use a smaller EPUB, or split a large ZIP import into smaller batches.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            return api_error_response(
                code=ErrorCode.INVALID_UPLOAD_TYPE,
                message="Invalid upload type.",
                detail=str(e),
                hint="Upload must be a .epub or .zip file.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


