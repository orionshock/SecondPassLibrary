from django.http import HttpResponse
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import ErrorCode, api_error_response
from marginalia.api import invalid_request_response
from marginalia.archives import (
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
)

from .apply import (
    ImportCandidateError,
    ImportReplayConflictError,
    StagedArchiveInvalidError,
    apply_import,
)
from .serializers import (
    MarginaliaImportApplySerializer,
    MarginaliaImportPreviewSerializer,
    MarginaliaImportUnmatchedQuerySerializer,
)
from .services import (
    ImportUploadTooLargeError,
    NoImportCandidatesError,
    preview_import,
)
from .staging import ImportStageStorageError, ImportStageUnavailableError
from .unmatched import (
    ZIP_FILENAME,
    NoDownloadableUnmatchedSessionsError,
    UnmatchedStageIntegrityError,
    UnmatchedZipAssemblyError,
    unmatched_archive_zip,
)


class MarginaliaImportPreviewView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MarginaliaImportPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = preview_import(user=request.user, **serializer.validated_data)
        except ImportUploadTooLargeError:
            return invalid_request_response(
                message="The import archive exceeds the 25 MiB limit.",
                hint="Choose a smaller archive and try again.",
            )
        except MalformedArchiveError:
            return invalid_request_response(
                message="The import archive must be valid UTF-8 JSON.",
                hint="Choose a Marginalia archive exported from Second Pass Library.",
            )
        except UnsupportedArchiveProfileError:
            return invalid_request_response(
                message="The import archive profile is not supported.",
                hint="Export a new archive from a supported Second Pass Library version.",
            )
        except ArchiveValidationError:
            return invalid_request_response(
                message="The import archive is invalid.",
                hint="Export a new archive from Second Pass Library and try again.",
            )
        except NoImportCandidatesError:
            return invalid_request_response(
                message="No Reading Sessions are available to import.",
                hint="Choose an archive that contains at least one Reading Session.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except ImportStageStorageError:
            return invalid_request_response(
                message="The import preview could not be staged.",
                hint="Try again. If it keeps failing, ask the server operator to check the application logs.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(preview)


class MarginaliaImportApplyView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MarginaliaImportApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = apply_import(user=request.user, **serializer.validated_data)
        except ImportStageUnavailableError:
            return api_error_response(
                code=ErrorCode.NOT_FOUND,
                message="The import stage is unavailable.",
                hint="Preview the archive again.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ImportCandidateError:
            return invalid_request_response(
                message="A selected Reading Session is not importable.",
                hint="Return to the preview, change the selection, and try again.",
            )
        except ImportReplayConflictError:
            return invalid_request_response(
                message="The import stage was already applied with a different request.",
                hint="Preview the archive again before importing.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except StagedArchiveInvalidError:
            return invalid_request_response(
                message="The staged import archive is no longer usable.",
                hint="Preview the archive again.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return Response(result)


class MarginaliaImportUnmatchedView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MarginaliaImportUnmatchedQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            content = unmatched_archive_zip(
                user=request.user,
                **serializer.validated_data,
            )
        except ImportStageUnavailableError:
            return api_error_response(
                code=ErrorCode.NOT_FOUND,
                message="The import stage is unavailable.",
                hint="Preview the archive again.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except NoDownloadableUnmatchedSessionsError:
            return invalid_request_response(
                message="No unmatched Reading Sessions are available to download.",
                hint="Return to the import preview and review its current matches.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except UnmatchedStageIntegrityError:
            return invalid_request_response(
                message="The staged import archive is no longer usable.",
                hint="Preview the archive again.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except UnmatchedZipAssemblyError:
            return invalid_request_response(
                message="The unmatched archive could not be assembled.",
                hint="Try again. If it keeps failing, ask the server operator to check the application logs.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = HttpResponse(content, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{ZIP_FILENAME}"'
        return response
