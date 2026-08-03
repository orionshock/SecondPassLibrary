from django.http import HttpResponse
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import ErrorCode, api_error_response
from marginalia.api import book_access_required_response, invalid_request_response
from marginalia.archives import (
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
)

from .apply import (
    ImportBookAccessRequiredError,
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
    DuplicateLibraryBookHashError,
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
                message="The import archive exceeds the 25 MiB limit."
            )
        except MalformedArchiveError:
            return invalid_request_response(
                message="The import archive must be valid UTF-8 JSON."
            )
        except UnsupportedArchiveProfileError:
            return invalid_request_response(
                message="The import archive profile is not supported."
            )
        except ArchiveValidationError:
            return invalid_request_response(
                message="The import archive does not satisfy the canonical contract."
            )
        except NoImportCandidatesError:
            return invalid_request_response(
                message="No Reading Sessions are available to import.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except DuplicateLibraryBookHashError:
            return invalid_request_response(
                message="Marginalia import found conflicting Library Book checksums.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except ImportStageStorageError:
            return invalid_request_response(
                message="The import preview could not be staged.",
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
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except ImportCandidateError:
            return invalid_request_response(
                message="A selected Reading Session is not importable."
            )
        except ImportBookAccessRequiredError as exc:
            response = book_access_required_response()
            response.data["error"].update(
                message=(
                    "Current Library access is required for one or more "
                    "selected Books."
                ),
                inaccessible_books=[{"title": title} for title in exc.titles],
                inaccessible_book_count=exc.total_count,
                inaccessible_books_truncated=exc.total_count > len(exc.titles),
            )
            return response
        except ImportReplayConflictError:
            return invalid_request_response(
                message="The import stage was already applied with a different request.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except StagedArchiveInvalidError:
            return invalid_request_response(
                message="The staged import archive is no longer usable.",
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
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except NoDownloadableUnmatchedSessionsError:
            return invalid_request_response(
                message="No unmatched Reading Sessions are available to download.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except UnmatchedStageIntegrityError:
            return invalid_request_response(
                message="The staged import archive is no longer usable.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except UnmatchedZipAssemblyError:
            return invalid_request_response(
                message="The unmatched archive could not be assembled.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = HttpResponse(content, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{ZIP_FILENAME}"'
        return response
