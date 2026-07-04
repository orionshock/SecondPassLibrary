from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from library import policies
from core.errors import ErrorCode, api_error_response

from .import_services import ImportResourceLimitError
from .services import create_import_result_from_upload
from .view_mixins import ClientBearerReadOnlyMixin

class ImportViewSet(
    ClientBearerReadOnlyMixin,
    viewsets.ViewSet,
):
    # Client bearer tokens should not be usable for imports (even read).
    client_bearer_allowed: dict[str, set[str]] = {}
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
        try:
            result = create_import_result_from_upload(
                user=request.user,
                uploaded_file=uploaded,
            )
        except ImportResourceLimitError as e:
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

        return Response(result.as_dict(), status=status.HTTP_201_CREATED)


