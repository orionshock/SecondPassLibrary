from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .import_apply_services import apply_marginalia_import
from .import_services import (
    MarginaliaImportPreviewError,
    parse_marginalia_json,
    preview_marginalia_import,
)


class MarginaliaImportPreviewView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {
                    "valid": False,
                    "errors": [{"path": "$.file", "message": "Upload a JSON file."}],
                    "can_apply": False,
                },
                status=400,
            )

        try:
            payload = parse_marginalia_json(uploaded.read())
            preview = preview_marginalia_import(user=request.user, payload=payload)
        except MarginaliaImportPreviewError as exc:
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
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {
                    "applied": False,
                    "errors": [{"path": "$.file", "message": "Upload a JSON file."}],
                },
                status=400,
            )

        try:
            payload = parse_marginalia_json(uploaded.read())
            result = apply_marginalia_import(user=request.user, payload=payload)
        except MarginaliaImportPreviewError as exc:
            return Response(
                {"applied": False, "valid": False, "errors": exc.errors},
                status=400,
            )

        return Response(result)
