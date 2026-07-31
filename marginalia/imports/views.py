from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from marginalia.api import invalid_request_response
from marginalia.archives import (
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
)

from .serializers import MarginaliaImportPreviewSerializer
from .services import (
    DuplicateLibraryBookHashError,
    ImportUploadTooLargeError,
    NoImportCandidatesError,
    preview_import,
)
from .staging import ImportStageStorageError


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
