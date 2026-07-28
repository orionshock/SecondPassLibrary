from __future__ import annotations

from django.http import HttpResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .apply import apply_marginalia_import
from .services import (
    MarginaliaImportError,
    NoDownloadableUnmatchedSessionsError,
    preview_marginalia_import,
    read_uploaded_marginalia_json,
    unmatched_marginalia_zip,
)
from .staging import (
    delete_staged_marginalia_import,
    load_staged_marginalia_import,
    stage_marginalia_import,
)


class MarginaliaImportPreviewView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            payload = read_uploaded_marginalia_json(request.FILES.get("file"))
            preview = preview_marginalia_import(user=request.user, payload=payload)
            preview["import_token"] = stage_marginalia_import(
                user=request.user,
                payload=payload,
            )
            if preview.get("unmatched_downloadable_session_count"):
                preview["unmatched_download_url"] = (
                    f"/api/v1/reading/import/unmatched/?import_token={preview['import_token']}"
                )
        except MarginaliaImportError as exc:
            return Response(
                {"valid": False, "errors": exc.errors, "can_apply": False},
                status=400,
            )

        return Response(preview)


class MarginaliaImportApplyView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("import_token")
        try:
            if not token:
                raise MarginaliaImportError(
                    "import_token is required.",
                    [{"path": "$.import_token", "message": "import_token is required."}],
                )
            payload = load_staged_marginalia_import(user=request.user, token=token)
            result = apply_marginalia_import(
                user=request.user,
                payload=payload,
                selection_raw=request.data.get("selection"),
            )
            delete_staged_marginalia_import(token=token)
        except MarginaliaImportError as exc:
            return Response(
                {"applied": False, "valid": False, "errors": exc.errors},
                status=400,
            )

        return Response(result)


class MarginaliaImportUnmatchedView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.query_params.get("import_token")
        try:
            payload = load_staged_marginalia_import(user=request.user, token=token)
            archive = unmatched_marginalia_zip(user=request.user, payload=payload)
        except NoDownloadableUnmatchedSessionsError as exc:
            return Response(
                {"valid": False, "errors": exc.errors},
                status=409,
            )
        except MarginaliaImportError as exc:
            return Response(
                {"valid": False, "errors": exc.errors},
                status=400,
            )

        response = HttpResponse(
            archive,
            content_type="application/zip",
        )
        response["Content-Disposition"] = (
            'attachment; filename="secondpass-marginalia-sessions.zip"'
        )
        return response
