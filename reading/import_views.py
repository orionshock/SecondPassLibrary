from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .import_apply_services import apply_marginalia_import
from .import_services import (
    MarginaliaImportError,
    preview_marginalia_import,
    read_uploaded_marginalia_json,
)
from .import_staging import (
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
            if token:
                payload = load_staged_marginalia_import(user=request.user, token=token)
            else:
                payload = read_uploaded_marginalia_json(request.FILES.get("file"))
            result = apply_marginalia_import(
                user=request.user,
                payload=payload,
                selection_raw=request.data.get("selection"),
            )
            if token:
                delete_staged_marginalia_import(token=token)
        except MarginaliaImportError as exc:
            return Response(
                {"applied": False, "valid": False, "errors": exc.errors},
                status=400,
            )

        return Response(result)
