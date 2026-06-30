from __future__ import annotations

import json

from django.http import HttpResponse
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
    unmatched_marginalia_export,
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
            if preview.get("unmatched_entries"):
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


class MarginaliaImportUnmatchedView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.query_params.get("import_token")
        try:
            payload = load_staged_marginalia_import(user=request.user, token=token)
            unmatched = unmatched_marginalia_export(user=request.user, payload=payload)
        except MarginaliaImportError as exc:
            return Response(
                {"valid": False, "errors": exc.errors},
                status=400,
            )

        response = HttpResponse(
            json.dumps(unmatched, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="second-pass-unmatched-marginalia.json"'
        return response
