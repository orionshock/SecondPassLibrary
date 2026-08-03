from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.errors import ErrorCode, api_error_response
from marginalia.api import invalid_request_response
from marginalia.archives import DuplicateBookHashError, MissingBookChecksumError

from .serializers import (
    MarginaliaExportQuerySerializer,
    MarginaliaSelectedExportSerializer,
)
from .services import (
    ExportTooLargeError,
    NoExportableSessionsError,
    SelectedSessionNotFoundError,
    export_all_marginalia,
    export_selected_marginalia,
)


class MarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MarginaliaExportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return self._export_response(
            lambda: export_all_marginalia(
                user=request.user,
                **serializer.validated_data,
            )
        )

    def post(self, request):
        serializer = MarginaliaSelectedExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return self._export_response(
                lambda: export_selected_marginalia(
                    user=request.user,
                    **serializer.validated_data,
                )
            )
        except SelectedSessionNotFoundError as exc:
            raise NotFound from exc

    @staticmethod
    def _export_response(build_document):
        try:
            document = build_document()
        except NoExportableSessionsError:
            return invalid_request_response(
                message="No Reading Sessions are available to export.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except ExportTooLargeError as exc:
            response = api_error_response(
                code=ErrorCode.EXPORT_TOO_LARGE,
                message="The Marginalia export is too large.",
                hint=(
                    "Use Selected Sessions and choose fewer Sessions, then try again."
                    if exc.mode == "full"
                    else "Choose fewer Sessions and try the export again."
                ),
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
            response.data["error"].update(
                export_mode=exc.mode,
                limit={"kind": exc.reason, "maximum": exc.maximum},
            )
            return response
        except MissingBookChecksumError:
            return invalid_request_response(
                message="Marginalia export requires a valid Book checksum.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except DuplicateBookHashError:
            return invalid_request_response(
                message="Marginalia export found conflicting Book checksums.",
                status_code=status.HTTP_409_CONFLICT,
            )

        filename_date = timezone.localtime(document.generated_at).strftime("%Y%m%d")
        response = HttpResponse(
            document.content,
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename_date}-second-pass-marginalia.json"'
        )
        return response
